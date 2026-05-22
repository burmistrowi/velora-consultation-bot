from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from bot.database.main import Database


class TemplateRule(Database.BASE):
    __tablename__ = "template_rules"

    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, nullable=False, index=True)

    # 0=Mon ... 6=Sun
    day_of_week = Column(Integer, nullable=False, index=True)

    # stored as "HH:MM"
    start_time = Column(String(5), nullable=False)
    end_time = Column(String(5), nullable=False)

    slot_duration = Column(Integer, nullable=False)  # minutes

    # Optional buffer between slots (minutes)
    break_minutes = Column(Integer, nullable=True)

    break_start = Column(String(5), nullable=True)
    break_end = Column(String(5), nullable=True)

    service_id = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

