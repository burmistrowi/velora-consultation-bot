from sqlalchemy import Column, Integer, String, Numeric, Boolean

from bot.database.main import Database
from bot.misc.env import settings


class Service(Database.BASE):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    price = Column(Numeric(10, 2), nullable=False)
    duration_min = Column(Integer, nullable=False)
    currency = Column(String(3), default=settings.CURRENCY, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

