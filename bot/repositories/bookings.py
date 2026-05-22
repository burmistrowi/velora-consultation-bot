from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from bot.database.main import Database
from bot.database.models.booking_meta import BookingMeta
from bot.database.models.slot import TimeSlot


class BookingRepository:
    def list_booked_for_day(self, day: datetime, *, status: str = "active") -> list[TimeSlot]:
        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)

        session = Database().session
        try:
            return (
                session.query(TimeSlot)
                .options(joinedload(TimeSlot.client))
                .filter(
                    and_(
                        TimeSlot.datetime >= start,
                        TimeSlot.datetime < end,
                        TimeSlot.status == status,
                    )
                )
                .order_by(TimeSlot.datetime.asc())
                .all()
            )
        finally:
            session.close()

    def get_meta(self, slot_id: int) -> BookingMeta | None:
        session = Database().session
        try:
            return session.query(BookingMeta).filter(BookingMeta.slot_id == slot_id).first()
        finally:
            session.close()

    def ensure_meta(self, slot_id: int) -> BookingMeta:
        session = Database().session
        try:
            meta = session.query(BookingMeta).filter(BookingMeta.slot_id == slot_id).first()
            if meta:
                return meta
            meta = BookingMeta(slot_id=slot_id)
            session.add(meta)
            session.commit()
            session.refresh(meta)
            return meta
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def set_confirmed(self, slot_id: int, *, confirmed: bool) -> bool:
        session = Database().session
        try:
            meta = session.query(BookingMeta).filter(BookingMeta.slot_id == slot_id).first()
            if not meta:
                meta = BookingMeta(slot_id=slot_id)
                session.add(meta)
                session.flush()
            meta.is_confirmed = confirmed
            meta.confirmed_at = datetime.utcnow() if confirmed else None
            # Mirror into time_slots fields used by reminders/expiration
            slot = session.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
            if slot:
                slot.is_confirmed = confirmed
                slot.confirmed_at = datetime.utcnow() if confirmed else None
                slot.confirmation_deadline = None if confirmed else slot.confirmation_deadline
                if confirmed and slot.status == "pending_confirmation":
                    slot.status = "active"
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def set_completed(self, slot_id: int, *, completed: bool) -> bool:
        session = Database().session
        try:
            meta = session.query(BookingMeta).filter(BookingMeta.slot_id == slot_id).first()
            if not meta:
                meta = BookingMeta(slot_id=slot_id)
                session.add(meta)
                session.flush()
            meta.is_completed = completed
            meta.completed_at = datetime.utcnow() if completed else None
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def set_charged_amount(self, slot_id: int, amount: float) -> None:
        session = Database().session
        try:
            meta = session.query(BookingMeta).filter(BookingMeta.slot_id == slot_id).first()
            if not meta:
                meta = BookingMeta(slot_id=slot_id)
                session.add(meta)
                session.flush()
            meta.charged_amount = amount
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def set_client_info(self, slot_id: int, *, name: str | None, phone: str | None, booked_service_id: int | None) -> None:
        session = Database().session
        try:
            meta = session.query(BookingMeta).filter(BookingMeta.slot_id == slot_id).first()
            if not meta:
                meta = BookingMeta(slot_id=slot_id)
                session.add(meta)
                session.flush()
            meta.client_name = name
            meta.client_phone = phone
            meta.booked_service_id = booked_service_id
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def move_meta(self, old_slot_id: int, new_slot_id: int) -> None:
        """
        Copies booking_meta from old slot to new slot and deletes old.
        """
        session = Database().session
        try:
            old = session.query(BookingMeta).filter(BookingMeta.slot_id == old_slot_id).first()
            if not old:
                return

            existing_new = session.query(BookingMeta).filter(BookingMeta.slot_id == new_slot_id).first()
            if existing_new:
                session.delete(existing_new)
                session.flush()

            new = BookingMeta(
                slot_id=new_slot_id,
                is_confirmed=old.is_confirmed,
                confirmed_at=old.confirmed_at,
                is_completed=old.is_completed,
                completed_at=old.completed_at,
                charged_amount=old.charged_amount,
                client_name=old.client_name,
                client_phone=old.client_phone,
                booked_service_id=old.booked_service_id,
                reminder_sent=False,
            )
            session.add(new)
            session.delete(old)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_for_reminders(self, now_utc: datetime, *, window_minutes: int = 10) -> list[tuple[TimeSlot, BookingMeta]]:
        """
        Returns booked slots starting in ~1 hour, with reminder_sent=false.
        Window: [now+60m, now+60m+window_minutes)
        """
        start = now_utc + timedelta(hours=1)
        end = start + timedelta(minutes=window_minutes)

        session = Database().session
        try:
            rows = (
                session.query(TimeSlot, BookingMeta)
                .join(BookingMeta, BookingMeta.slot_id == TimeSlot.id)
                .options(joinedload(TimeSlot.client))
                .filter(
                    and_(
                        TimeSlot.status == "active",
                        TimeSlot.datetime >= start,
                        TimeSlot.datetime < end,
                        BookingMeta.reminder_sent == False,  # noqa: E712
                        BookingMeta.is_confirmed == True,  # noqa: E712
                        TimeSlot.client_id.isnot(None),
                    )
                )
                .order_by(TimeSlot.datetime.asc())
                .all()
            )
            return rows
        finally:
            session.close()

    def list_pending_expired(self, now: datetime) -> list[TimeSlot]:
        """
        Returns pending_confirmation slots with passed deadline.
        """
        session = Database().session
        try:
            return (
                session.query(TimeSlot)
                .options(joinedload(TimeSlot.client))
                .filter(
                    and_(
                        TimeSlot.status == "pending_confirmation",
                        TimeSlot.confirmation_deadline.isnot(None),
                        TimeSlot.confirmation_deadline < now,
                    )
                )
                .order_by(TimeSlot.confirmation_deadline.asc())
                .all()
            )
        finally:
            session.close()

    def mark_reminder_sent(self, slot_id: int) -> None:
        session = Database().session
        try:
            meta = session.query(BookingMeta).filter(BookingMeta.slot_id == slot_id).first()
            if not meta:
                meta = BookingMeta(slot_id=slot_id)
                session.add(meta)
                session.flush()
            meta.reminder_sent = True
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

