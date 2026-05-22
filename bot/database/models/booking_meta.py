from sqlalchemy import BigInteger, Column, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint, Numeric, String
from datetime import datetime

from bot.database.main import Database


class BookingMeta(Database.BASE):
    __tablename__ = "booking_meta"
    __table_args__ = (UniqueConstraint("slot_id", name="uq_booking_meta_slot_id"),)

    id = Column(Integer, primary_key=True)
    slot_id = Column(Integer, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False)

    # Reschedule tracking (HIGH priority request)
    business_id = Column(Integer, nullable=False, default=1, index=True)
    client_id = Column(BigInteger, nullable=True, index=True)
    old_slot_id = Column(Integer, nullable=True, index=True)
    new_slot_id = Column(Integer, nullable=True, index=True)
    status = Column(String(20), nullable=True, index=True)  # pending | completed | cancelled
    created_by = Column(BigInteger, nullable=True, index=True)
    new_appointment_id = Column(Integer, nullable=True, index=True)

    is_confirmed = Column(Boolean, default=False, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)

    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    charged_amount = Column(Numeric(10, 2), nullable=True)
    client_name = Column(String(255), nullable=True)
    client_phone = Column(String(32), nullable=True)
    booked_service_id = Column(Integer, nullable=True)
    reminder_sent = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

