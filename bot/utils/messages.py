from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message


logger = logging.getLogger(__name__)


async def send_auto_delete_message(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    delay: int = 2,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    """
    Sends a message and auto-deletes it after `delay` seconds.
    Intended for short-lived notifications only (not menus/calendars/input prompts).
    """
    try:
        msg = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    except Exception as e:
        logger.exception("send_auto_delete_message send failed chat_id=%s: %s", chat_id, e)
        return None

    async def _delete_later(message_id: int) -> None:
        try:
            await asyncio.sleep(delay)
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            # Ignore delete failures (already deleted / can't delete / etc.)
            return

    asyncio.create_task(_delete_later(msg.message_id))
    return msg

