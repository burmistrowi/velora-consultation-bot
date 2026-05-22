from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from bot.database.main import Database


class ScheduleTemplate(Database.BASE):
    __tablename__ = "schedule_templates"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, nullable=False, index=True, default=1)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

