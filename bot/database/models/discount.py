from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from bot.database.main import Database
from bot.misc.env import settings


class Discount(Database.BASE):
    """
    Discount is user-scoped by username (requested in requirements).
    - type: all | selected
    - amount_type: percent | fixed
    - amount_value: percent (0..100) or fixed amount in currency
    """

    __tablename__ = "discounts"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), nullable=False, index=True)

    applies_to = Column(String(20), default="all", nullable=False)  # all | selected
    amount_type = Column(String(10), nullable=False)  # percent | fixed
    amount_value = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default=settings.CURRENCY, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DiscountService(Database.BASE):
    __tablename__ = "discount_services"

    id = Column(Integer, primary_key=True)
    discount_id = Column(Integer, ForeignKey("discounts.id", ondelete="CASCADE"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)

    discount = relationship("Discount", backref="service_links")

