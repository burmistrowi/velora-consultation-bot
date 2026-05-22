from sqlalchemy.exc import NoResultFound
from bot.database.main import Database
from bot.database.models.user import User
from bot.database.models.slot import TimeSlot
from datetime import datetime
from bot.misc.env import settings

def create_user(chat_id: int, username: str) -> User:
    """Creates a new user in the database or returns None if user already exists"""
    session = Database().session
    try:
        # Check if user already exists
        existing_user = session.query(User).filter(User.chat_id == chat_id).first()
        if existing_user:
            return None
            
        user = User(
            chat_id=chat_id,
            username=username,
        )
        session.add(user)
        session.commit()
        return user
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def create_slot(slot_datetime: datetime, *, service_id: int | None = None) -> TimeSlot:
    """Creates a new time slot"""
    session = Database().session
    try:
        new_slot = TimeSlot(
            business_id=1,
            datetime=slot_datetime,
            currency=settings.CURRENCY,
            service_id=service_id,
            status="available",
            is_available=True,
            client_id=None,
            is_confirmed=False,
            confirmed_at=None,
            confirmation_deadline=None,
        )
        session.add(new_slot)
        session.commit()
        return new_slot
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()