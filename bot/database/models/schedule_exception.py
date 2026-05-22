from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from bot.database.main import Database


class ScheduleException(Database.BASE):
    __tablename__ = "schedule_exceptions"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, nullable=False, index=True, default=1)

    # stored as YYYY-MM-DD
    exception_date = Column(String(10), nullable=False, index=True)
    exception_type = Column(String(20), nullable=False)  # off | special

    start_time = Column(String(5), nullable=True)
    end_time = Column(String(5), nullable=True)
    slot_duration = Column(Integer, nullable=True)
    service_id = Column(Integer, nullable=True, index=True)
    reason = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

