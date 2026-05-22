from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer

from bot.database.main import Database


class SupportConversation(Database.BASE):
    __tablename__ = "support_conversations"

    business_id = Column(Integer, primary_key=True)
    client_id = Column(BigInteger, primary_key=True)

    unread_count = Column(Integer, nullable=False, default=0)
    last_message_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

