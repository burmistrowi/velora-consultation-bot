from sqlalchemy import Column, Integer, BigInteger, String, DateTime
from datetime import datetime

from bot.database.main import Database


class AdminUser(Database.BASE):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    role = Column(String(20), default="admin", nullable=False)  # admin | owner
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

