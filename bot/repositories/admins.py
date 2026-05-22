from __future__ import annotations

from typing import Optional

from bot.database.main import Database
from bot.database.models.admin_user import AdminUser


class AdminRepository:
    def list(self) -> list[AdminUser]:
        session = Database().session
        try:
            return session.query(AdminUser).order_by(AdminUser.role.desc(), AdminUser.created_at.asc()).all()
        finally:
            session.close()

    def get_by_chat_id(self, chat_id: int) -> Optional[AdminUser]:
        session = Database().session
        try:
            return session.query(AdminUser).filter(AdminUser.chat_id == chat_id).first()
        finally:
            session.close()

    def get_by_username(self, username: str) -> Optional[AdminUser]:
        session = Database().session
        try:
            return session.query(AdminUser).filter(AdminUser.username == username).first()
        finally:
            session.close()

    def add(self, *, chat_id: int, username: str | None, role: str = "admin") -> AdminUser:
        session = Database().session
        try:
            admin = AdminUser(chat_id=chat_id, username=username, role=role)
            session.add(admin)
            session.commit()
            session.refresh(admin)
            return admin
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete(self, admin_id: int) -> bool:
        session = Database().session
        try:
            admin = session.query(AdminUser).filter(AdminUser.id == admin_id).first()
            if not admin:
                return False
            session.delete(admin)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

