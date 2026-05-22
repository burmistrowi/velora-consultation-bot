from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, text
from sqlalchemy.exc import IntegrityError

from bot.database.main import Database
from bot.database.models.slot import TimeSlot


def _parse_hhmm(v: str | None) -> time | None:
    if not v:
        return None
    hh, mm = v.split(":")
    return time(hour=int(hh), minute=int(mm))


def _daterange(start: date, end_exclusive: date):
    d = start
    while d < end_exclusive:
        yield d
        d = d + timedelta(days=1)


@dataclass(frozen=True)
class GenerateResult:
    created: int
    skipped_existing: int
    deleted_overwritten: int


@dataclass(frozen=True)
class PreviewExample:
    dt: datetime
    service_id: int | None
    is_exception: bool


@dataclass(frozen=True)
class PreviewResult:
    from_date: date
    to_date_exclusive: date
    estimated_total: int
    examples: list[PreviewExample]


class SlotGenerator:
    def __init__(self):
        self._db = Database()

    def generate_slots_from_template(
        self,
        *,
        template_id: int,
        start_date: date,
        weeks_ahead: int,
        overwrite: bool,
    ) -> GenerateResult:
        """
        Generates available slots for weeks ahead starting from start_date (inclusive).
        - Supports rules per weekday
        - Supports break window
        - Supports exceptions: off and special schedules
        """
        if weeks_ahead < 2:
            weeks_ahead = 2
        if weeks_ahead > 8:
            weeks_ahead = 8

        end_date = start_date + timedelta(weeks=weeks_ahead)

        session = self._db.session
        created = 0
        skipped = 0
        deleted = 0
        try:
            tpl = session.execute(
                text("SELECT id, business_id, is_active FROM schedule_templates WHERE id=:id"),
                {"id": template_id},
            ).mappings().first()
            if not tpl or int(tpl["is_active"] or 0) != 1:
                return GenerateResult(created=0, skipped_existing=0, deleted_overwritten=0)

            business_id = int(tpl["business_id"] or 1)

            rules = session.execute(
                text(
                    """
                    SELECT id, day_of_week, start_time, end_time, slot_duration, break_minutes, break_start, break_end, service_id
                    FROM template_rules
                    WHERE template_id=:tid
                    ORDER BY day_of_week ASC, start_time ASC
                    """
                ),
                {"tid": template_id},
            ).mappings().all()

            exc = session.execute(
                text(
                    """
                    SELECT exception_date, exception_type, start_time, end_time, slot_duration, service_id
                    FROM schedule_exceptions
                    WHERE business_id=:bid
                      AND exception_date >= :from_d
                      AND exception_date < :to_d
                    """
                ),
                {"bid": business_id, "from_d": start_date.isoformat(), "to_d": end_date.isoformat()},
            ).mappings().all()
            exceptions_by_date: dict[str, list[dict]] = {}
            for e in exc:
                exceptions_by_date.setdefault(str(e["exception_date"]), []).append(dict(e))

            if overwrite:
                # delete previously generated available slots in range for this template
                res = session.query(TimeSlot).filter(
                    and_(
                        TimeSlot.business_id == business_id,
                        TimeSlot.datetime >= datetime.combine(start_date, time(0, 0)),
                        TimeSlot.datetime < datetime.combine(end_date, time(0, 0)),
                        TimeSlot.status == "available",
                        TimeSlot.is_available == True,  # noqa: E712
                        TimeSlot.generated_from_template_id == template_id,
                    )
                ).delete(synchronize_session=False)
                deleted = int(res or 0)

            # Build per-weekday rules
            rules_by_dow: dict[int, list[dict]] = {}
            for r in rules:
                rules_by_dow.setdefault(int(r["day_of_week"]), []).append(dict(r))

            for d in _daterange(start_date, end_date):
                d_iso = d.isoformat()
                # Exceptions override rules
                if d_iso in exceptions_by_date:
                    for e in exceptions_by_date[d_iso]:
                        if e["exception_type"] == "off":
                            continue
                        created, skipped = self._generate_for_window(
                            session,
                            business_id=business_id,
                            dt_date=d,
                            start_time=_parse_hhmm(e.get("start_time")),
                            end_time=_parse_hhmm(e.get("end_time")),
                            slot_duration=int(e.get("slot_duration") or 60),
                            break_start=None,
                            break_end=None,
                            service_id=int(e.get("service_id") or 0) or None,
                            template_id=template_id,
                            rule_id=None,
                            is_exception=True,
                            created=created,
                            skipped=skipped,
                        )
                    continue

                dow = d.weekday()
                day_rules = rules_by_dow.get(dow) or []
                for r in day_rules:
                    created, skipped = self._generate_for_window(
                        session,
                        business_id=business_id,
                        dt_date=d,
                        start_time=_parse_hhmm(r.get("start_time")),
                        end_time=_parse_hhmm(r.get("end_time")),
                        slot_duration=int(r.get("slot_duration") or 60),
                        break_minutes=int(r.get("break_minutes") or 0),
                        break_start=_parse_hhmm(r.get("break_start")),
                        break_end=_parse_hhmm(r.get("break_end")),
                        service_id=int(r.get("service_id") or 0) or None,
                        template_id=template_id,
                        rule_id=int(r["id"]),
                        is_exception=False,
                        created=created,
                        skipped=skipped,
                    )

            session.commit()
            return GenerateResult(created=created, skipped_existing=skipped, deleted_overwritten=deleted)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _generate_for_window(
        self,
        session,
        *,
        business_id: int,
        dt_date: date,
        start_time: time | None,
        end_time: time | None,
        slot_duration: int,
        break_minutes: int,
        break_start: time | None,
        break_end: time | None,
        service_id: int | None,
        template_id: int,
        rule_id: int | None,
        is_exception: bool,
        created: int,
        skipped: int,
    ) -> tuple[int, int]:
        if not start_time or not end_time:
            return created, skipped
        if slot_duration <= 0:
            slot_duration = 60
        if break_minutes < 0:
            break_minutes = 0

        start_dt = datetime.combine(dt_date, start_time)
        end_dt = datetime.combine(dt_date, end_time)
        b_start = datetime.combine(dt_date, break_start) if break_start else None
        b_end = datetime.combine(dt_date, break_end) if break_end else None

        cur = start_dt
        while cur + timedelta(minutes=slot_duration) <= end_dt:
            # break skip
            if b_start and b_end and (cur >= b_start and cur < b_end):
                cur = b_end
                continue

            slot = TimeSlot(
                business_id=business_id,
                datetime=cur,
                is_available=True,
                client_id=None,
                status="available",
                service_id=service_id,
                is_confirmed=False,
                confirmed_at=None,
                confirmation_deadline=None,
                generated_from_template_id=template_id,
                generated_from_rule_id=rule_id,
                is_exception=is_exception,
            )
            try:
                with session.begin_nested():
                    session.add(slot)
                    session.flush()
                created += 1
            except IntegrityError:
                skipped += 1
            cur = cur + timedelta(minutes=slot_duration + break_minutes)
        return created, skipped

    def preview_slots_from_template(
        self,
        *,
        template_id: int,
        start_date: date,
        weeks_ahead: int,
        max_examples: int = 3,
    ) -> PreviewResult:
        """
        Returns an estimated count of slots that would be created (ignores duplicates in DB),
        and a few example slots for UX preview before generation.
        """
        if weeks_ahead < 1:
            weeks_ahead = 1
        if weeks_ahead > 8:
            weeks_ahead = 8
        end_date = start_date + timedelta(weeks=weeks_ahead)

        session = self._db.session
        try:
            tpl = session.execute(
                text("SELECT id, business_id, is_active FROM schedule_templates WHERE id=:id"),
                {"id": template_id},
            ).mappings().first()
            if not tpl or int(tpl["is_active"] or 0) != 1:
                return PreviewResult(from_date=start_date, to_date_exclusive=end_date, estimated_total=0, examples=[])

            business_id = int(tpl["business_id"] or 1)
            rules = session.execute(
                text(
                    """
                    SELECT id, day_of_week, start_time, end_time, slot_duration, break_minutes, break_start, break_end, service_id
                    FROM template_rules
                    WHERE template_id=:tid
                    ORDER BY day_of_week ASC, start_time ASC
                    """
                ),
                {"tid": template_id},
            ).mappings().all()

            exc = session.execute(
                text(
                    """
                    SELECT exception_date, exception_type, start_time, end_time, slot_duration, service_id
                    FROM schedule_exceptions
                    WHERE business_id=:bid
                      AND exception_date >= :from_d
                      AND exception_date < :to_d
                    """
                ),
                {"bid": business_id, "from_d": start_date.isoformat(), "to_d": end_date.isoformat()},
            ).mappings().all()
            exceptions_by_date: dict[str, list[dict]] = {}
            for e in exc:
                exceptions_by_date.setdefault(str(e["exception_date"]), []).append(dict(e))

            rules_by_dow: dict[int, list[dict]] = {}
            for r in rules:
                rules_by_dow.setdefault(int(r["day_of_week"]), []).append(dict(r))

            total = 0
            examples: list[PreviewExample] = []

            def _collect(dt: datetime, sid: int | None, is_exc: bool) -> None:
                nonlocal examples
                if len(examples) >= max_examples:
                    return
                examples.append(PreviewExample(dt=dt, service_id=sid, is_exception=is_exc))

            for d in _daterange(start_date, end_date):
                d_iso = d.isoformat()
                if d_iso in exceptions_by_date:
                    for e in exceptions_by_date[d_iso]:
                        if e["exception_type"] == "off":
                            continue
                        inc, ex = self._preview_for_window(
                            dt_date=d,
                            start_time=_parse_hhmm(e.get("start_time")),
                            end_time=_parse_hhmm(e.get("end_time")),
                            slot_duration=int(e.get("slot_duration") or 60),
                            break_minutes=0,
                            break_start=None,
                            break_end=None,
                            service_id=int(e.get("service_id") or 0) or None,
                            max_examples=max_examples - len(examples),
                        )
                        total += inc
                        for dt in ex:
                            _collect(dt, int(e.get("service_id") or 0) or None, True)
                    continue

                dow = d.weekday()
                for r in rules_by_dow.get(dow) or []:
                    inc, ex = self._preview_for_window(
                        dt_date=d,
                        start_time=_parse_hhmm(r.get("start_time")),
                        end_time=_parse_hhmm(r.get("end_time")),
                        slot_duration=int(r.get("slot_duration") or 60),
                        break_minutes=int(r.get("break_minutes") or 0),
                        break_start=_parse_hhmm(r.get("break_start")),
                        break_end=_parse_hhmm(r.get("break_end")),
                        service_id=int(r.get("service_id") or 0) or None,
                        max_examples=max_examples - len(examples),
                    )
                    total += inc
                    for dt in ex:
                        _collect(dt, int(r.get("service_id") or 0) or None, False)
            return PreviewResult(
                from_date=start_date,
                to_date_exclusive=end_date,
                estimated_total=total,
                examples=examples,
            )
        finally:
            session.close()

    def _preview_for_window(
        self,
        *,
        dt_date: date,
        start_time: time | None,
        end_time: time | None,
        slot_duration: int,
        break_minutes: int,
        break_start: time | None,
        break_end: time | None,
        service_id: int | None,
        max_examples: int,
    ) -> tuple[int, list[datetime]]:
        if not start_time or not end_time:
            return 0, []
        if slot_duration <= 0:
            slot_duration = 60
        if break_minutes < 0:
            break_minutes = 0

        start_dt = datetime.combine(dt_date, start_time)
        end_dt = datetime.combine(dt_date, end_time)
        b_start = datetime.combine(dt_date, break_start) if break_start else None
        b_end = datetime.combine(dt_date, break_end) if break_end else None

        cur = start_dt
        count = 0
        examples: list[datetime] = []
        while cur + timedelta(minutes=slot_duration) <= end_dt:
            if b_start and b_end and (cur >= b_start and cur < b_end):
                cur = b_end
                continue
            count += 1
            if len(examples) < max_examples:
                examples.append(cur)
            cur = cur + timedelta(minutes=slot_duration + break_minutes)
        return count, examples

