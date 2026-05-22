from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import desc, func
from sqlalchemy import and_

from bot.database.main import Database
from bot.database.models.support_conversation import SupportConversation
from bot.database.models.support_message import SupportMessage


@dataclass(frozen=True)
class SupportThread:
    business_id: int
    client_id: int
    client_username: str | None
    unread_count: int
    last_text: str
    last_at: str


class SupportRepository:
    DEFAULT_BUSINESS_ID = 1

    def _upsert_conversation(self, session, *, business_id: int, client_id: int, inc_unread: bool, last_at) -> None:
        conv = (
            session.query(SupportConversation)
            .filter(and_(SupportConversation.business_id == business_id, SupportConversation.client_id == client_id))
            .first()
        )
        if not conv:
            conv = SupportConversation(
                business_id=business_id,
                client_id=client_id,
                unread_count=1 if inc_unread else 0,
                last_message_at=last_at,
                is_active=True,
            )
            session.add(conv)
            session.flush()
            return
        conv.last_message_at = last_at
        conv.is_active = True
        if inc_unread:
            conv.unread_count = int(conv.unread_count or 0) + 1

    def create_client_message(
        self,
        *,
        business_id: int | None,
        client_id: int,
        client_username: str | None,
        message: str,
        reply_to_id: int | None = None,
    ) -> SupportMessage:
        session = Database().session
        try:
            bid = business_id or self.DEFAULT_BUSINESS_ID
            m = SupportMessage(
                business_id=bid,
                client_id=client_id,
                client_username=client_username,
                admin_id=None,
                message=message,
                is_from_client=True,
                is_read=False,
                reply_to_id=reply_to_id,
            )
            session.add(m)
            session.flush()
            self._upsert_conversation(session, business_id=bid, client_id=client_id, inc_unread=True, last_at=m.created_at)
            session.commit()
            session.refresh(m)
            return m
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_admin_reply(
        self,
        *,
        business_id: int | None,
        client_id: int,
        client_username: str | None,
        admin_id: int,
        message: str,
        reply_to_id: int | None = None,
    ) -> SupportMessage:
        session = Database().session
        try:
            bid = business_id or self.DEFAULT_BUSINESS_ID
            m = SupportMessage(
                business_id=bid,
                client_id=client_id,
                client_username=client_username,
                admin_id=admin_id,
                message=message,
                is_from_client=False,
                # unread for client until they open inbox / acknowledge
                is_read=False,
                reply_to_id=reply_to_id,
            )
            session.add(m)
            session.flush()
            # Admin reply does not increase unread_count for admins; it only updates last_message_at.
            self._upsert_conversation(session, business_id=bid, client_id=client_id, inc_unread=False, last_at=m.created_at)
            session.commit()
            session.refresh(m)
            return m
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, message_id: int) -> Optional[SupportMessage]:
        session = Database().session
        try:
            return session.query(SupportMessage).filter(SupportMessage.id == message_id).first()
        finally:
            session.close()

    def soft_delete_message(self, *, message_id: int, admin_id: int) -> bool:
        """
        Soft delete: replace message text, keep row for audit/history.
        """
        session = Database().session
        try:
            m = session.query(SupportMessage).filter(SupportMessage.id == message_id).first()
            if not m:
                return False
            m.message = f"🗑 Сообщение удалено администратором (ID {admin_id})."
            m.is_read = True
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def soft_delete_client_message(self, *, message_id: int, client_id: int) -> bool:
        """
        Client can delete only own messages.
        """
        session = Database().session
        try:
            m = session.query(SupportMessage).filter(SupportMessage.id == message_id).first()
            if not m:
                return False
            if int(m.client_id) != int(client_id) or not m.is_from_client:
                return False
            m.message = "🗑 Сообщение удалено."
            m.is_read = True
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_threads(self, *, limit: int = 20) -> list[SupportThread]:
        session = Database().session
        try:
            convs = (
                session.query(SupportConversation)
                .order_by(desc(SupportConversation.last_message_at))
                .limit(limit)
                .all()
            )

            threads: list[SupportThread] = []
            for c in convs:
                last = (
                    session.query(SupportMessage)
                    .filter(
                        and_(
                            SupportMessage.business_id == c.business_id,
                            SupportMessage.client_id == c.client_id,
                        )
                    )
                    .order_by(SupportMessage.created_at.desc())
                    .first()
                )
                if not last:
                    continue
                threads.append(
                    SupportThread(
                        business_id=int(c.business_id),
                        client_id=int(c.client_id),
                        client_username=last.client_username,
                        unread_count=int(c.unread_count or 0),
                        last_text=(last.message[:60] + "…") if len(last.message) > 60 else last.message,
                        last_at=last.created_at.strftime("%d.%m %H:%M"),
                    )
                )
            return threads
        finally:
            session.close()

    def list_messages(self, *, business_id: int | None, client_id: int, limit: int = 30) -> list[SupportMessage]:
        session = Database().session
        try:
            bid = business_id or self.DEFAULT_BUSINESS_ID
            return (
                session.query(SupportMessage)
                .filter(and_(SupportMessage.business_id == bid, SupportMessage.client_id == client_id))
                .order_by(SupportMessage.created_at.desc())
                .limit(limit)
                .all()
            )[::-1]
        finally:
            session.close()

    def get_last_unread_client_message(self, *, business_id: int | None, client_id: int) -> SupportMessage | None:
        """
        Last unread message from client (for admin UI).
        """
        session = Database().session
        try:
            bid = business_id or self.DEFAULT_BUSINESS_ID
            return (
                session.query(SupportMessage)
                .filter(
                    and_(
                        SupportMessage.business_id == bid,
                        SupportMessage.client_id == client_id,
                        SupportMessage.is_from_client == True,  # noqa: E712
                        SupportMessage.is_read == False,  # noqa: E712
                    )
                )
                .order_by(SupportMessage.created_at.desc())
                .first()
            )
        finally:
            session.close()

    def get_last_unread_admin_message(self, *, business_id: int | None, client_id: int) -> SupportMessage | None:
        """
        Last unread message from admin (for client UI).
        """
        session = Database().session
        try:
            bid = business_id or self.DEFAULT_BUSINESS_ID
            return (
                session.query(SupportMessage)
                .filter(
                    and_(
                        SupportMessage.business_id == bid,
                        SupportMessage.client_id == client_id,
                        SupportMessage.is_from_client == False,  # noqa: E712
                        SupportMessage.is_read == False,  # noqa: E712
                    )
                )
                .order_by(SupportMessage.created_at.desc())
                .first()
            )
        finally:
            session.close()

    def mark_client_messages_read(self, *, business_id: int | None, client_id: int) -> None:
        session = Database().session
        try:
            bid = business_id or self.DEFAULT_BUSINESS_ID
            session.query(SupportMessage).filter(
                and_(
                    SupportMessage.business_id == bid,
                    SupportMessage.client_id == client_id,
                    SupportMessage.is_from_client == True,  # noqa: E712
                    SupportMessage.is_read == False,  # noqa: E712
                )
            ).update({"is_read": True})
            conv = (
                session.query(SupportConversation)
                .filter(and_(SupportConversation.business_id == bid, SupportConversation.client_id == client_id))
                .first()
            )
            if conv:
                conv.unread_count = 0
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def mark_admin_messages_read(self, *, business_id: int | None, client_id: int) -> None:
        """
        Marks admin->client messages as read by the client.
        """
        session = Database().session
        try:
            bid = business_id or self.DEFAULT_BUSINESS_ID
            session.query(SupportMessage).filter(
                and_(
                    SupportMessage.business_id == bid,
                    SupportMessage.client_id == client_id,
                    SupportMessage.is_from_client == False,  # noqa: E712
                    SupportMessage.is_read == False,  # noqa: E712
                )
            ).update({"is_read": True})
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def unread_for_client(self, *, business_id: int | None, client_id: int) -> int:
        """
        Unread admin replies for a client.
        """
        session = Database().session
        try:
            bid = business_id or self.DEFAULT_BUSINESS_ID
            v = (
                session.query(func.count(SupportMessage.id))
                .filter(
                    and_(
                        SupportMessage.business_id == bid,
                        SupportMessage.client_id == client_id,
                        SupportMessage.is_from_client == False,  # noqa: E712
                        SupportMessage.is_read == False,  # noqa: E712
                    )
                )
                .scalar()
            )
            return int(v or 0)
        finally:
            session.close()

    def unread_total(self, *, business_id: int | None = None) -> int:
        session = Database().session
        try:
            bid = business_id or self.DEFAULT_BUSINESS_ID
            v = (
                session.query(func.coalesce(func.sum(SupportConversation.unread_count), 0))
                .filter(SupportConversation.business_id == bid)
                .scalar()
            )
            return int(v or 0)
        finally:
            session.close()

