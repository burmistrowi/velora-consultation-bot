from aiogram import Bot
import logging
from datetime import datetime

from bot.misc.env import settings
from bot.keyboards.inline.notifications import admin_notification_kb
from bot.utils.messages import send_auto_delete_message

logger = logging.getLogger(__name__)

async def notify_admins_booking_created(bot: Bot, slot_datetime: datetime, client_info: str):
    """Sends notification to admins about created booking"""
    for admin_id in settings.admin_ids:
        try:
            await send_auto_delete_message(
                bot,
                admin_id,
                f"✅ Новая запись\n"
                f"📅 Дата: {slot_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                f"👤 Клиент: {client_info}",
                delay=2,
                reply_markup=admin_notification_kb(),
            )
        except Exception:
            logger.warning("Failed to notify admin %s about new booking", admin_id, exc_info=True)

async def notify_admins_booking_cancelled(bot: Bot, slot_datetime: datetime, client_info: str):
    """Sends notification to admins about cancelled booking"""
    for admin_id in settings.admin_ids:
        try:
            await send_auto_delete_message(
                bot,
                admin_id,
                f"❌ Отменена консультация\n"
                f"📅 Дата: {slot_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                f"👤 Клиент: {client_info}",
                delay=2,
                reply_markup=admin_notification_kb(),
            )
        except Exception:
            logger.warning("Failed to notify admin %s about cancelled booking", admin_id, exc_info=True) 