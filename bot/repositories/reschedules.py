from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from bot.database.main import Database


class RescheduleRepository:
    """
    Stores reschedule history in booking_reschedules (created by runtime migration).
    """

    def add(self, *, old_slot_id: int, new_slot_id: int, actor_chat_id: int | None) -> None:
        session = Database().session
        try:
            session.execute(
                text(
                    """
                    INSERT INTO booking_reschedules (old_slot_id, new_slot_id, actor_chat_id, created_at, rolled_back)
                    VALUES (:old, :new, :actor, :ts, 0)
                    """
                ),
                {"old": old_slot_id, "new": new_slot_id, "actor": actor_chat_id, "ts": datetime.utcnow()},
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def last_for_old(self, *, old_slot_id: int) -> dict | None:
        session = Database().session
        try:
            row = session.execute(
                text(
                    """
                    SELECT id, old_slot_id, new_slot_id, actor_chat_id, created_at, rolled_back, rolled_back_at
                    FROM booking_reschedules
                    WHERE old_slot_id = :old
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"old": old_slot_id},
            ).mappings().first()
            return dict(row) if row else None
        finally:
            session.close()

    def last_for_new(self, *, new_slot_id: int) -> dict | None:
        session = Database().session
        try:
            row = session.execute(
                text(
                    """
                    SELECT id, old_slot_id, new_slot_id, actor_chat_id, created_at, rolled_back, rolled_back_at
                    FROM booking_reschedules
                    WHERE new_slot_id = :new
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"new": new_slot_id},
            ).mappings().first()
            return dict(row) if row else None
        finally:
            session.close()

    def list_for_slot(self, *, slot_id: int) -> list[dict]:
        session = Database().session
        try:
            rows = session.execute(
                text(
                    """
                    SELECT id, old_slot_id, new_slot_id, actor_chat_id, created_at, rolled_back, rolled_back_at
                    FROM booking_reschedules
                    WHERE old_slot_id = :sid OR new_slot_id = :sid
                    ORDER BY id DESC
                    """
                ),
                {"sid": slot_id},
            ).mappings().all()
            return [dict(r) for r in rows]
        finally:
            session.close()

    def mark_rolled_back(self, *, reschedule_id: int) -> None:
        session = Database().session
        try:
            session.execute(
                text(
                    """
                    UPDATE booking_reschedules
                    SET rolled_back = 1, rolled_back_at = :ts
                    WHERE id = :id
                    """
                ),
                {"id": reschedule_id, "ts": datetime.utcnow()},
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

