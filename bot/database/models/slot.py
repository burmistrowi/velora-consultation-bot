from sqlalchemy import Column, Integer, DateTime, Boolean, ForeignKey, String
from sqlalchemy.orm import relationship
from bot.database.main import Database
from bot.misc.env import settings
from datetime import datetime, timedelta

class TimeSlot(Database.BASE):
    __tablename__ = 'time_slots'
    
    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, nullable=False, default=1)
    datetime = Column(DateTime, nullable=False)
    is_available = Column(Boolean, default=True)
    client_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    # Status lifecycle:
    # - available: free slot
    # - pending_confirmation: reserved, waiting for client confirmation
    # - active: confirmed appointment
    # - cancelled: cancelled appointment (kept for history)
    # - rescheduled: appointment was moved to another slot (kept for history)
    # - completed: completed appointment
    status = Column(String(50), default='available')
    currency = Column(String(3), default=lambda: settings.CURRENCY)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)

    # Generated schedule metadata
    generated_from_template_id = Column(Integer, nullable=True, index=True)
    generated_from_rule_id = Column(Integer, nullable=True, index=True)
    is_exception = Column(Boolean, default=False, nullable=False)

    # Confirmation fields (requested HIGH priority)
    is_confirmed = Column(Boolean, default=False, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    confirmation_deadline = Column(DateTime, nullable=True)
    
    client = relationship("User", back_populates="bookings")