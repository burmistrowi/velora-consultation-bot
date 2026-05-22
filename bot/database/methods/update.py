from typing import Optional
from sqlalchemy.exc import NoResultFound
from bot.database.main import Database
from bot.database.models.user import User
from bot.database.models.slot import TimeSlot
from bot.database.models.booking_meta import BookingMeta
from datetime import datetime
from aiogram import Bot
from sqlalchemy import and_
from sqlalchemy import text
from bot.misc.env import settings
import logging

logger = logging.getLogger(__name__)

def update_user(chat_id: int, username: Optional[str] = None) -> bool:
    """Updates user information"""
    session = Database().session
    try:
        user = session.query(User).filter(User.chat_id == chat_id).one()
        if username is not None:
            user.username = username
        session.commit()
        return True
    except NoResultFound:
        return False
    finally:
        session.close()

def book_slot(slot_id: int, user_id: int, *, status: str = "pending_confirmation", confirmation_deadline: datetime | None = None) -> bool:
    """
    Atomic reservation to prevent double-bookings.

    - PostgreSQL: UPDATE ... WHERE ... RETURNING id
    - SQLite: BEGIN IMMEDIATE + UPDATE + check rowcount
    """
    session = Database().session
    try:
        now = datetime.now()
        dialect = session.bind.dialect.name  # type: ignore[union-attr]

        if dialect.startswith("postgres"):
            # Atomic claim
            res = session.execute(
                text(
                    """
                    UPDATE time_slots
                    SET
                        is_available = FALSE,
                        client_id = :user_id,
                        status = :status,
                        is_confirmed = FALSE,
                        confirmed_at = NULL,
                        confirmation_deadline = :deadline
                    WHERE
                        id = :slot_id
                        AND status = 'available'
                        AND is_available = TRUE
                        AND datetime > :now
                    RETURNING id
                    """
                ),
                {"user_id": user_id, "status": status, "deadline": confirmation_deadline, "slot_id": slot_id, "now": now},
            ).scalar()
            session.commit()
            return bool(res)

        if dialect == "sqlite":
            # Lock DB for writers and claim slot atomically
            session.execute(text("BEGIN IMMEDIATE"))
            res = session.execute(
                text(
                    """
                    UPDATE time_slots
                    SET
                        is_available = 0,
                        client_id = :user_id,
                        status = :status,
                        is_confirmed = 0,
                        confirmed_at = NULL,
                        confirmation_deadline = :deadline
                    WHERE
                        id = :slot_id
                        AND status = 'available'
                        AND is_available = 1
                        AND datetime > :now
                    """
                ),
                {"user_id": user_id, "status": status, "deadline": confirmation_deadline, "slot_id": slot_id, "now": now},
            )
            ok = int(getattr(res, "rowcount", 0) or 0) == 1
            session.commit()
            return ok

        # Fallback: best-effort
        slot = session.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
        if slot and slot.is_available and slot.status == "available" and slot.datetime > now:
            slot.is_available = False
            slot.client_id = user_id
            slot.status = status
            slot.is_confirmed = False
            slot.confirmed_at = None
            slot.confirmation_deadline = confirmation_deadline
            session.commit()
            return True
        return False
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def cancel_booking(slot_id: int) -> bool:
    """Отмена активной/ожидающей записи: один раз помечаем слот и создаём новый свободный (без дубля при гонке)."""
    session = Database().session
    try:
        dialect = session.bind.dialect.name  # type: ignore[union-attr]

        if dialect.startswith("postgres"):
            row = session.execute(
                text(
                    """
                    UPDATE time_slots
                    SET
                        status = 'cancelled',
                        is_available = FALSE,
                        is_confirmed = FALSE,
                        confirmed_at = NULL,
                        confirmation_deadline = NULL
                    WHERE
                        id = :sid
                        AND status IN ('active', 'pending_confirmation')
                    RETURNING datetime, service_id, currency, business_id
                    """
                ),
                {"sid": slot_id},
            ).mappings().first()
            if not row:
                session.rollback()
                return False
            session.add(
                TimeSlot(
                    business_id=int(row["business_id"] or 1),
                    datetime=row["datetime"],
                    is_available=True,
                    client_id=None,
                    status="available",
                    currency=row["currency"] or settings.CURRENCY,
                    service_id=row["service_id"],
                    is_confirmed=False,
                    confirmed_at=None,
                    confirmation_deadline=None,
                )
            )
            session.commit()
            return True

        if dialect == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
            upd = session.execute(
                text(
                    """
                    UPDATE time_slots
                    SET
                        status = 'cancelled',
                        is_available = 0,
                        is_confirmed = 0,
                        confirmed_at = NULL,
                        confirmation_deadline = NULL
                    WHERE
                        id = :sid
                        AND status IN ('active', 'pending_confirmation')
                    """
                ),
                {"sid": slot_id},
            )
            if int(getattr(upd, "rowcount", 0) or 0) != 1:
                session.rollback()
                return False
            row = session.execute(
                text(
                    "SELECT datetime, service_id, currency, business_id FROM time_slots WHERE id = :sid"
                ),
                {"sid": slot_id},
            ).mappings().first()
            if not row:
                session.rollback()
                return False
            session.add(
                TimeSlot(
                    business_id=int(row["business_id"] or 1),
                    datetime=row["datetime"],
                    is_available=True,
                    client_id=None,
                    status="available",
                    currency=row["currency"] or settings.CURRENCY,
                    service_id=row["service_id"],
                    is_confirmed=False,
                    confirmed_at=None,
                    confirmation_deadline=None,
                )
            )
            session.commit()
            return True

        # Fallback: прежняя логика (не рекомендуется для продакшена)
        slot = session.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
        if not slot or slot.status not in ("active", "pending_confirmation"):
            return False
        old_dt = slot.datetime
        old_service_id = getattr(slot, "service_id", None)
        old_currency = getattr(slot, "currency", settings.CURRENCY)
        bid = int(getattr(slot, "business_id", 1) or 1)
        slot.status = "cancelled"
        slot.is_available = False
        slot.is_confirmed = False
        slot.confirmed_at = None
        slot.confirmation_deadline = None
        session.commit()
        session.add(
            TimeSlot(
                business_id=bid,
                datetime=old_dt,
                is_available=True,
                client_id=None,
                status="available",
                currency=old_currency,
                service_id=old_service_id,
                is_confirmed=False,
                confirmed_at=None,
                confirmation_deadline=None,
            )
        )
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.exception("Error cancelling booking slot_id=%s: %s", slot_id, e)
        return False
    finally:
        session.close()

def release_slot(slot_id: int) -> bool:
    """
    Backward-compatible alias: previously "release" meant cancel.
    Now it performs cancellation (status='cancelled') and recreates an available slot.
    """
    return cancel_booking(slot_id)


def reschedule_booking(old_slot_id: int) -> bool:
    """
    Marks an appointment as rescheduled (kept for history) and restores availability
    by cloning a new free slot at the same datetime/service.
    """
    session = Database().session
    try:
        slot = session.query(TimeSlot).filter(TimeSlot.id == old_slot_id).first()
        if not slot or slot.status not in ("active", "pending_confirmation"):
            return False

        old_dt = slot.datetime
        old_service_id = getattr(slot, "service_id", None)
        old_currency = getattr(slot, "currency", settings.CURRENCY)

        slot.status = "rescheduled"
        slot.is_available = False
        slot.confirmation_deadline = None
        session.commit()

        new_slot = TimeSlot(
            business_id=getattr(slot, "business_id", 1),
            datetime=old_dt,
            is_available=True,
            client_id=None,
            status="available",
            currency=old_currency,
            service_id=old_service_id,
            is_confirmed=False,
            confirmed_at=None,
            confirmation_deadline=None,
        )
        session.add(new_slot)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.exception("Error rescheduling booking slot_id=%s: %s", old_slot_id, e)
        return False
    finally:
        session.close()


def atomic_reschedule(
    *,
    business_id: int,
    old_slot_id: int,
    new_slot_id: int,
    created_by: int,
) -> bool:
    """
    Atomic reschedule:
    - lock old+new rows
    - create booking_meta reschedule record (status='pending')
    - mark old appointment as rescheduled (keep history)
    - create new available slot at old datetime (free schedule)
    - claim new slot as active appointment for same client
    - update booking_meta status='completed'
    """
    session = Database().session
    try:
        dialect = session.bind.dialect.name  # type: ignore[union-attr]
        now = datetime.now()

        if dialect.startswith("postgres"):
            session.execute(text("BEGIN"))
            old = session.execute(
                text("SELECT * FROM time_slots WHERE id=:id FOR UPDATE"),
                {"id": old_slot_id},
            ).mappings().first()
            new = session.execute(
                text("SELECT * FROM time_slots WHERE id=:id FOR UPDATE"),
                {"id": new_slot_id},
            ).mappings().first()
            if not old or not new:
                session.rollback()
                return False
            if old["status"] not in ("active", "pending_confirmation") or not old.get("client_id"):
                session.rollback()
                return False
            if new["status"] != "available" or not new.get("is_available"):
                session.rollback()
                return False

            # guard against double reschedule
            session.execute(
                text(
                    """
                    INSERT INTO booking_meta (slot_id, business_id, client_id, old_slot_id, new_slot_id, status, created_by, created_at)
                    VALUES (:slot_id, :business_id, :client_id, :old_slot_id, :new_slot_id, 'pending', :created_by, NOW())
                    ON CONFLICT (slot_id) DO UPDATE SET
                        business_id=EXCLUDED.business_id,
                        client_id=EXCLUDED.client_id,
                        old_slot_id=EXCLUDED.old_slot_id,
                        new_slot_id=EXCLUDED.new_slot_id,
                        status='pending',
                        created_by=EXCLUDED.created_by
                    """
                ),
                {
                    "slot_id": old_slot_id,
                    "business_id": business_id,
                    "client_id": old["client_id"],
                    "old_slot_id": old_slot_id,
                    "new_slot_id": new_slot_id,
                    "created_by": created_by,
                },
            )

            session.execute(
                text("UPDATE time_slots SET status='rescheduled', is_available=FALSE, confirmation_deadline=NULL WHERE id=:id"),
                {"id": old_slot_id},
            )
            # free schedule at old datetime by inserting a new available slot
            session.execute(
                text(
                    """
                    INSERT INTO time_slots (business_id, datetime, is_available, client_id, status, currency, service_id, is_confirmed)
                    VALUES (:business_id, :dt, TRUE, NULL, 'available', :currency, :service_id, FALSE)
                    """
                ),
                {"business_id": business_id, "dt": old["datetime"], "currency": old.get("currency"), "service_id": old.get("service_id")},
            )

            # claim new slot as active appointment
            updated = session.execute(
                text(
                    """
                    UPDATE time_slots
                    SET
                        is_available=FALSE,
                        client_id=:client_id,
                        status='active',
                        is_confirmed=TRUE,
                        confirmed_at=NOW(),
                        confirmation_deadline=NULL
                    WHERE id=:id AND status='available' AND is_available=TRUE
                    RETURNING id
                    """
                ),
                {"id": new_slot_id, "client_id": old["client_id"]},
            ).scalar()
            if not updated:
                session.rollback()
                return False

            session.execute(
                text(
                    """
                    UPDATE booking_meta
                    SET status='completed', new_appointment_id=:new_id, new_slot_id=:new_id
                    WHERE slot_id=:old_id
                    """
                ),
                {"old_id": old_slot_id, "new_id": new_slot_id},
            )
            session.commit()
            return True

        # SQLite path
        if dialect == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
            old = session.execute(text("SELECT * FROM time_slots WHERE id=:id"), {"id": old_slot_id}).mappings().first()
            new = session.execute(text("SELECT * FROM time_slots WHERE id=:id"), {"id": new_slot_id}).mappings().first()
            if not old or not new:
                session.rollback()
                return False
            if old["status"] not in ("active", "pending_confirmation") or not old.get("client_id"):
                session.rollback()
                return False
            if new["status"] != "available" or int(new.get("is_available") or 0) != 1:
                session.rollback()
                return False

            session.execute(
                text(
                    """
                    INSERT OR REPLACE INTO booking_meta (slot_id, business_id, client_id, old_slot_id, new_slot_id, status, created_by, created_at)
                    VALUES (:slot_id, :business_id, :client_id, :old_slot_id, :new_slot_id, 'pending', :created_by, CURRENT_TIMESTAMP)
                    """
                ),
                {
                    "slot_id": old_slot_id,
                    "business_id": business_id,
                    "client_id": old["client_id"],
                    "old_slot_id": old_slot_id,
                    "new_slot_id": new_slot_id,
                    "created_by": created_by,
                },
            )

            session.execute(
                text("UPDATE time_slots SET status='rescheduled', is_available=0, confirmation_deadline=NULL WHERE id=:id"),
                {"id": old_slot_id},
            )
            session.execute(
                text(
                    """
                    INSERT INTO time_slots (business_id, datetime, is_available, client_id, status, currency, service_id, is_confirmed)
                    VALUES (:business_id, :dt, 1, NULL, 'available', :currency, :service_id, 0)
                    """
                ),
                {"business_id": business_id, "dt": old["datetime"], "currency": old.get("currency"), "service_id": old.get("service_id")},
            )
            res = session.execute(
                text(
                    """
                    UPDATE time_slots
                    SET is_available=0, client_id=:client_id, status='active', is_confirmed=1, confirmed_at=CURRENT_TIMESTAMP, confirmation_deadline=NULL
                    WHERE id=:id AND status='available' AND is_available=1
                    """
                ),
                {"id": new_slot_id, "client_id": old["client_id"]},
            )
            if int(getattr(res, "rowcount", 0) or 0) != 1:
                session.rollback()
                return False
            session.execute(
                text("UPDATE booking_meta SET status='completed', new_appointment_id=:new_id, new_slot_id=:new_id WHERE slot_id=:old_id"),
                {"old_id": old_slot_id, "new_id": new_slot_id},
            )
            session.commit()
            return True

        return False
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def cancel_reschedule(*, old_slot_id: int) -> bool:
    """
    Cancels a pending reschedule by setting booking_meta.status='cancelled'.
    (Does not revert slots automatically; intended as guard for double reschedules.)
    """
    session = Database().session
    try:
        m = session.query(BookingMeta).filter(BookingMeta.slot_id == old_slot_id, BookingMeta.status == "pending").first()
        if not m:
            return False
        m.status = "cancelled"
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
