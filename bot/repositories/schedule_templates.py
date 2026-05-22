from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import text

from bot.database.main import Database


@dataclass(frozen=True)
class TemplateRow:
    id: int
    business_id: int
    name: str
    is_active: bool


@dataclass(frozen=True)
class RuleRow:
    id: int
    template_id: int
    day_of_week: int
    start_time: str
    end_time: str
    slot_duration: int
    break_minutes: Optional[int]
    break_start: Optional[str]
    break_end: Optional[str]
    service_id: Optional[int]


@dataclass(frozen=True)
class ExceptionRow:
    id: int
    business_id: int
    exception_date: str
    exception_type: str
    start_time: Optional[str]
    end_time: Optional[str]
    slot_duration: Optional[int]
    service_id: Optional[int]
    reason: Optional[str]


class ScheduleTemplateRepository:
    def list_templates(self, *, business_id: int = 1, active_only: bool = False) -> list[TemplateRow]:
        session = Database().session
        try:
            sql = "SELECT id, business_id, name, is_active FROM schedule_templates WHERE business_id=:bid"
            params = {"bid": business_id}
            if active_only:
                sql += " AND is_active=1" if session.bind.dialect.name == "sqlite" else " AND is_active=TRUE"
            sql += " ORDER BY id DESC"
            rows = session.execute(text(sql), params).mappings().all()
            return [
                TemplateRow(
                    id=int(r["id"]),
                    business_id=int(r["business_id"]),
                    name=str(r["name"]),
                    is_active=bool(r["is_active"]),
                )
                for r in rows
            ]
        finally:
            session.close()

    def get_template(self, template_id: int) -> Optional[TemplateRow]:
        session = Database().session
        try:
            r = session.execute(
                text("SELECT id, business_id, name, is_active FROM schedule_templates WHERE id=:id"),
                {"id": template_id},
            ).mappings().first()
            if not r:
                return None
            return TemplateRow(
                id=int(r["id"]),
                business_id=int(r["business_id"]),
                name=str(r["name"]),
                is_active=bool(r["is_active"]),
            )
        finally:
            session.close()

    def create_template(self, *, business_id: int, name: str) -> int:
        session = Database().session
        try:
            dialect = session.bind.dialect.name
            if dialect.startswith("postgres"):
                new_id = session.execute(
                    text(
                        "INSERT INTO schedule_templates (business_id, name, is_active) VALUES (:bid, :name, TRUE) RETURNING id"
                    ),
                    {"bid": business_id, "name": name},
                ).scalar_one()
            else:
                session.execute(
                    text("INSERT INTO schedule_templates (business_id, name, is_active) VALUES (:bid, :name, 1)"),
                    {"bid": business_id, "name": name},
                )
                new_id = session.execute(text("SELECT last_insert_rowid()")).scalar_one()
            session.commit()
            return int(new_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update_template(self, template_id: int, *, name: str | None = None, is_active: bool | None = None) -> bool:
        session = Database().session
        try:
            tpl = session.execute(text("SELECT id FROM schedule_templates WHERE id=:id"), {"id": template_id}).first()
            if not tpl:
                return False
            if name is not None:
                session.execute(text("UPDATE schedule_templates SET name=:name WHERE id=:id"), {"name": name, "id": template_id})
            if is_active is not None:
                session.execute(
                    text("UPDATE schedule_templates SET is_active=:a WHERE id=:id"),
                    {"a": bool(is_active), "id": template_id},
                )
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_template(self, template_id: int) -> bool:
        session = Database().session
        try:
            res = session.execute(text("DELETE FROM schedule_templates WHERE id=:id"), {"id": template_id})
            session.commit()
            return bool(res.rowcount)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_rules(self, template_id: int) -> list[RuleRow]:
        session = Database().session
        try:
            rows = session.execute(
                text(
                    """
                    SELECT id, template_id, day_of_week, start_time, end_time, slot_duration, break_minutes, break_start, break_end, service_id
                    FROM template_rules
                    WHERE template_id=:tid
                    ORDER BY day_of_week ASC, start_time ASC
                    """
                ),
                {"tid": template_id},
            ).mappings().all()
            return [
                RuleRow(
                    id=int(r["id"]),
                    template_id=int(r["template_id"]),
                    day_of_week=int(r["day_of_week"]),
                    start_time=str(r["start_time"]),
                    end_time=str(r["end_time"]),
                    slot_duration=int(r["slot_duration"]),
                    break_minutes=int(r["break_minutes"]) if r["break_minutes"] is not None else None,
                    break_start=r["break_start"],
                    break_end=r["break_end"],
                    service_id=int(r["service_id"]) if r["service_id"] is not None else None,
                )
                for r in rows
            ]
        finally:
            session.close()

    def get_rule(self, rule_id: int) -> Optional[RuleRow]:
        session = Database().session
        try:
            r = session.execute(
                text(
                    """
                    SELECT id, template_id, day_of_week, start_time, end_time, slot_duration, break_minutes, break_start, break_end, service_id
                    FROM template_rules
                    WHERE id=:id
                    """
                ),
                {"id": rule_id},
            ).mappings().first()
            if not r:
                return None
            return RuleRow(
                id=int(r["id"]),
                template_id=int(r["template_id"]),
                day_of_week=int(r["day_of_week"]),
                start_time=str(r["start_time"]),
                end_time=str(r["end_time"]),
                slot_duration=int(r["slot_duration"]),
                break_minutes=int(r["break_minutes"]) if r["break_minutes"] is not None else None,
                break_start=r["break_start"],
                break_end=r["break_end"],
                service_id=int(r["service_id"]) if r["service_id"] is not None else None,
            )
        finally:
            session.close()

    def add_rule(
        self,
        *,
        template_id: int,
        day_of_week: int,
        start_time: str,
        end_time: str,
        slot_duration: int,
        break_start: str | None,
        break_end: str | None,
        service_id: int | None,
    ) -> int:
        session = Database().session
        try:
            dialect = session.bind.dialect.name
            if dialect.startswith("postgres"):
                new_id = session.execute(
                    text(
                        """
                        INSERT INTO template_rules
                            (template_id, day_of_week, start_time, end_time, slot_duration, break_minutes, break_start, break_end, service_id)
                        VALUES
                            (:tid, :dow, :st, :et, :dur, :bmin, :bst, :bet, :sid)
                        RETURNING id
                        """
                    ),
                    {
                        "tid": template_id,
                        "dow": day_of_week,
                        "st": start_time,
                        "et": end_time,
                        "dur": slot_duration,
                        "bmin": None,
                        "bst": break_start,
                        "bet": break_end,
                        "sid": service_id,
                    },
                ).scalar_one()
            else:
                session.execute(
                    text(
                        """
                        INSERT INTO template_rules
                            (template_id, day_of_week, start_time, end_time, slot_duration, break_minutes, break_start, break_end, service_id)
                        VALUES
                            (:tid, :dow, :st, :et, :dur, :bmin, :bst, :bet, :sid)
                        """
                    ),
                    {
                        "tid": template_id,
                        "dow": day_of_week,
                        "st": start_time,
                        "et": end_time,
                        "dur": slot_duration,
                        "bmin": None,
                        "bst": break_start,
                        "bet": break_end,
                        "sid": service_id,
                    },
                )
                new_id = session.execute(text("SELECT last_insert_rowid()")).scalar_one()
            session.commit()
            return int(new_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update_rule(
        self,
        rule_id: int,
        *,
        day_of_week: int,
        start_time: str,
        end_time: str,
        slot_duration: int,
        break_minutes: int | None,
        break_start: str | None,
        break_end: str | None,
        service_id: int | None,
    ) -> bool:
        session = Database().session
        try:
            exists = session.execute(text("SELECT id FROM template_rules WHERE id=:id"), {"id": rule_id}).first()
            if not exists:
                return False
            session.execute(
                text(
                    """
                    UPDATE template_rules
                    SET day_of_week=:dow,
                        start_time=:st,
                        end_time=:et,
                        slot_duration=:dur,
                        break_minutes=:bmin,
                        break_start=:bst,
                        break_end=:bet,
                        service_id=:sid
                    WHERE id=:id
                    """
                ),
                {
                    "id": rule_id,
                    "dow": day_of_week,
                    "st": start_time,
                    "et": end_time,
                    "dur": slot_duration,
                    "bmin": break_minutes,
                    "bst": break_start,
                    "bet": break_end,
                    "sid": service_id,
                },
            )
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_rule(self, rule_id: int) -> bool:
        session = Database().session
        try:
            res = session.execute(text("DELETE FROM template_rules WHERE id=:id"), {"id": rule_id})
            session.commit()
            return bool(res.rowcount)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_exceptions(self, *, business_id: int = 1, from_date: date | None = None) -> list[ExceptionRow]:
        session = Database().session
        try:
            sql = """
                SELECT id, business_id, exception_date, exception_type, start_time, end_time, slot_duration, service_id, reason
                FROM schedule_exceptions
                WHERE business_id=:bid
            """
            params = {"bid": business_id}
            if from_date:
                sql += " AND exception_date >= :from_d"
                params["from_d"] = from_date.isoformat()
            sql += " ORDER BY exception_date ASC, id ASC"
            rows = session.execute(text(sql), params).mappings().all()
            return [
                ExceptionRow(
                    id=int(r["id"]),
                    business_id=int(r["business_id"]),
                    exception_date=str(r["exception_date"]),
                    exception_type=str(r["exception_type"]),
                    start_time=r["start_time"],
                    end_time=r["end_time"],
                    slot_duration=int(r["slot_duration"]) if r["slot_duration"] is not None else None,
                    service_id=int(r["service_id"]) if r["service_id"] is not None else None,
                    reason=r["reason"],
                )
                for r in rows
            ]
        finally:
            session.close()

    def add_exception(
        self,
        *,
        business_id: int,
        exception_date: str,
        exception_type: str,
        start_time: str | None,
        end_time: str | None,
        slot_duration: int | None,
        service_id: int | None,
        reason: str | None,
    ) -> int:
        session = Database().session
        try:
            dialect = session.bind.dialect.name
            if dialect.startswith("postgres"):
                new_id = session.execute(
                    text(
                        """
                        INSERT INTO schedule_exceptions
                            (business_id, exception_date, exception_type, start_time, end_time, slot_duration, service_id, reason)
                        VALUES
                            (:bid, :d, :t, :st, :et, :dur, :sid, :r)
                        RETURNING id
                        """
                    ),
                    {"bid": business_id, "d": exception_date, "t": exception_type, "st": start_time, "et": end_time, "dur": slot_duration, "sid": service_id, "r": reason},
                ).scalar_one()
            else:
                session.execute(
                    text(
                        """
                        INSERT INTO schedule_exceptions
                            (business_id, exception_date, exception_type, start_time, end_time, slot_duration, service_id, reason)
                        VALUES
                            (:bid, :d, :t, :st, :et, :dur, :sid, :r)
                        """
                    ),
                    {"bid": business_id, "d": exception_date, "t": exception_type, "st": start_time, "et": end_time, "dur": slot_duration, "sid": service_id, "r": reason},
                )
                new_id = session.execute(text("SELECT last_insert_rowid()")).scalar_one()
            session.commit()
            return int(new_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_exception(self, exception_id: int) -> bool:
        session = Database().session
        try:
            res = session.execute(text("DELETE FROM schedule_exceptions WHERE id=:id"), {"id": exception_id})
            session.commit()
            return bool(res.rowcount)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

