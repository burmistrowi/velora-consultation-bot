from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


class DeleteUserMessageMiddleware(BaseMiddleware):
    """В личном чате сразу удаляет входящие сообщения пользователя (чистый диалог)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.chat.type == ChatType.PRIVATE:
            u = event.from_user
            if u is not None and not u.is_bot:
                try:
                    await event.delete()
                except TelegramBadRequest as e:
                    logger.debug("Не удалось удалить сообщение пользователя: %s", e)
        return await handler(event, data)
