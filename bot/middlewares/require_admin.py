"""Принудительная проверка админа для всего роутера (например, расписание без IsAdmin на каждом хендлере)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.services.admin_access import get_admin_chat_ids_cached


class RequireAdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        uid = getattr(getattr(event, "from_user", None), "id", None)
        if uid is None or uid not in get_admin_chat_ids_cached():
            if isinstance(event, CallbackQuery):
                await event.answer("Недостаточно прав.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Недостаточно прав.")
            return None
        return await handler(event, data)
