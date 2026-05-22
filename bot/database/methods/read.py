from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from bot.database.main import Database
from bot.database.models.user import User
from bot.database.models.slot import TimeSlot

def get_user_by_chat_id(chat_id: int) -> Optional[User]:
    """Gets user by chat ID"""
    session = Database().session
    try:
        return session.query(User).filter(User.chat_id == chat_id).first()
    finally:
        session.close()


def get_user_by_username(username: str) -> Optional[User]:
    """Gets user by Telegram username (without @)"""
    session = Database().session
    try:
        uname = username.lstrip("@")
        return session.query(User).filter(User.username == uname).first()
    finally:
        session.close()

def get_available_slots(from_date: datetime, to_date: datetime) -> List[TimeSlot]:
    """Gets available time slots between two dates"""
    session = Database().session
    try:
        return session.query(TimeSlot).filter(
            and_(
                TimeSlot.datetime.between(from_date, to_date),
                TimeSlot.is_available == True,
                TimeSlot.status == 'available',
                TimeSlot.datetime > datetime.now()
            )
        ).order_by(TimeSlot.datetime).all()
    finally:
        session.close()

def get_slot_by_id(slot_id: int) -> Optional[TimeSlot]:
    """Gets time slot by ID"""
    session = Database().session
    try:
        return (
            session.query(TimeSlot)
            .options(joinedload(TimeSlot.client))
            .filter(TimeSlot.id == slot_id)
            .first()
        )
    finally:
        session.close()

def get_user_bookings(user_id: int) -> List[TimeSlot]:
    """Gets all bookings for a user"""
    session = Database().session
    try:
        return session.query(TimeSlot).filter(
            and_(
                TimeSlot.client_id == user_id,
                TimeSlot.status == 'active',
                TimeSlot.datetime >= datetime.now()
            )
        ).order_by(TimeSlot.datetime).all()
    finally:
        session.close()


def get_user_upcoming_appointments(user_id: int) -> List[TimeSlot]:
    """
    Gets upcoming appointments for a user, including:
    - active (confirmed)
    - pending_confirmation (awaiting confirmation)
    """
    session = Database().session
    try:
        return (
            session.query(TimeSlot)
            .filter(
                and_(
                    TimeSlot.client_id == user_id,
                    TimeSlot.status.in_(["active", "pending_confirmation"]),
                    TimeSlot.datetime >= datetime.now(),
                )
            )
            .order_by(TimeSlot.datetime)
            .all()
        )
    finally:
        session.close()

def get_all_slots(from_date: datetime = None) -> List[TimeSlot]:
    """Gets all time slots"""
    session = Database().session
    try:
        query = session.query(TimeSlot)
        if from_date:
            query = query.filter(TimeSlot.datetime >= from_date)
        return query.order_by(TimeSlot.datetime).all()
    finally:
        session.close()

def check_user_booking_limit(user_id: int, limit: int) -> bool:
    """True, если пользователь ещё может создать запись: активные + ожидающие подтверждения < limit."""
    session = Database().session
    try:
        active_bookings = session.query(TimeSlot).filter(
            and_(
                TimeSlot.client_id == user_id,
                TimeSlot.datetime >= datetime.now(),
                TimeSlot.status.in_(["active", "pending_confirmation"]),
            )
        ).count()
        return active_bookings < limit
    finally:
        session.close()

def get_booked_slots(datetime_check: datetime) -> List[TimeSlot]:
    """Gets all booked slots for a specific datetime"""
    session = Database().session
    try:
        return session.query(TimeSlot).filter(
            and_(
                TimeSlot.status == 'active',
                TimeSlot.datetime >= datetime_check,
                TimeSlot.datetime < datetime_check + timedelta(hours=1)
            )
        ).all()
    finally:
        session.close()

#
# Payment-related read helpers removed (YooKassa removed).
#
