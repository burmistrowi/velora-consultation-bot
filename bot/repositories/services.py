from __future__ import annotations

from typing import Iterable, Optional

from bot.database.main import Database
from bot.database.models.service import Service


class ServiceRepository:
    def list(self, *, active_only: bool = True) -> list[Service]:
        session = Database().session
        try:
            q = session.query(Service)
            if active_only:
                q = q.filter(Service.is_active == True)  # noqa: E712
            return q.order_by(Service.name.asc()).all()
        finally:
            session.close()

    def get(self, service_id: int) -> Optional[Service]:
        session = Database().session
        try:
            return session.query(Service).filter(Service.id == service_id).first()
        finally:
            session.close()

    def create(self, *, name: str, price: float, duration_min: int) -> Service:
        session = Database().session
        try:
            service = Service(name=name, price=price, duration_min=duration_min)
            session.add(service)
            session.commit()
            session.refresh(service)
            return service
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update(
        self,
        service_id: int,
        *,
        name: str,
        price: float,
        duration_min: int,
        is_active: bool = True,
    ) -> bool:
        session = Database().session
        try:
            service = session.query(Service).filter(Service.id == service_id).first()
            if not service:
                return False
            service.name = name
            service.price = price
            service.duration_min = duration_min
            service.is_active = is_active
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete(self, service_id: int) -> bool:
        session = Database().session
        try:
            service = session.query(Service).filter(Service.id == service_id).first()
            if not service:
                return False
            session.delete(service)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

