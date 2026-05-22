from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text

from bot.database.main import Database


class SupportMessage(Database.BASE):
    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True)

    business_id = Column(Integer, nullable=False, index=True, default=1)
    client_id = Column(BigInteger, nullable=False, index=True)
    client_username = Column(String(255), nullable=True)

    admin_id = Column(BigInteger, nullable=True, index=True)

    message = Column(Text, nullable=False)
    is_from_client = Column(Boolean, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    reply_to_id = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

