from __future__ import annotations

from typing import Optional

from sqlalchemy import and_

from bot.database.main import Database
from bot.database.models.discount import Discount, DiscountService


class DiscountRepository:
    def list(self, *, active_only: bool = True) -> list[Discount]:
        session = Database().session
        try:
            q = session.query(Discount)
            if active_only:
                q = q.filter(Discount.is_active == True)  # noqa: E712
            return q.order_by(Discount.created_at.desc()).all()
        finally:
            session.close()

    def get(self, discount_id: int) -> Optional[Discount]:
        session = Database().session
        try:
            return session.query(Discount).filter(Discount.id == discount_id).first()
        finally:
            session.close()

    def get_active_for_username(self, username: str) -> Optional[Discount]:
        session = Database().session
        try:
            return (
                session.query(Discount)
                .filter(and_(Discount.username == username, Discount.is_active == True))  # noqa: E712
                .order_by(Discount.created_at.desc())
                .first()
            )
        finally:
            session.close()

    def create(
        self,
        *,
        username: str,
        applies_to: str,
        amount_type: str,
        amount_value: float,
        service_ids: list[int] | None = None,
    ) -> Discount:
        session = Database().session
        try:
            discount = Discount(
                username=username.lstrip("@"),
                applies_to=applies_to,
                amount_type=amount_type,
                amount_value=amount_value,
            )
            session.add(discount)
            session.flush()

            if applies_to == "selected" and service_ids:
                session.add_all([DiscountService(discount_id=discount.id, service_id=sid) for sid in service_ids])

            session.commit()
            session.refresh(discount)
            return discount
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete(self, discount_id: int) -> bool:
        session = Database().session
        try:
            discount = session.query(Discount).filter(Discount.id == discount_id).first()
            if not discount:
                return False
            session.delete(discount)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_selected_service_ids(self, discount_id: int) -> list[int]:
        session = Database().session
        try:
            return [
                r.service_id
                for r in session.query(DiscountService).filter(DiscountService.discount_id == discount_id).all()
            ]
        finally:
            session.close()

