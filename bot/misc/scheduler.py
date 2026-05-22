from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import SERVICE_EMOJI
from bot.utils.ru_labels import service_display_name
from bot.repositories.bookings import BookingRepository
from bot.repositories.services import ServiceRepository
from bot.database.methods.update import cancel_booking
from bot.keyboards.inline.notifications import notification_kb


logger = logging.getLogger(__name__)


def setup_reminders(bot):
    scheduler = AsyncIOScheduler()

    async def check_upcoming_bookings():
        now = datetime.now(timezone.utc)
        repo = BookingRepository()
        rows = repo.list_for_reminders(now, window_minutes=10)
        if not rows:
            return

        services_map = {s.id: s.name for s in ServiceRepository().list(active_only=False)}

        for slot, meta in rows:
            if not slot.client:
                continue
            service_id = meta.booked_service_id or getattr(slot, "service_id", None)
            raw_name = services_map.get(service_id) if service_id else None
            service_name = service_display_name(raw_name)

            try:
                await bot.send_message(
                    slot.client.chat_id,
                    f"⏰ Напоминание: через 1 час у вас запись.\n\n"
                    f"🕐 Время: {slot.datetime.strftime('%d.%m.%Y %H:%M')}\n"
                    f"{SERVICE_EMOJI} Услуга: {service_name}",
                    reply_markup=notification_kb(),
                )
                repo.mark_reminder_sent(slot.id)
            except Exception as e:
                logger.exception("Failed to send reminder for slot_id=%s: %s", slot.id, e)

    scheduler.add_job(check_upcoming_bookings, "interval", minutes=10)

    async def expire_pending_confirmations():
        """
        Auto-cancel pending confirmations past deadline.
        Runs every minute.
        """
        now = datetime.now()
        repo = BookingRepository()
        expired = repo.list_pending_expired(now)
        if not expired:
            return

        for slot in expired:
            try:
                ok = cancel_booking(slot.id)
                if ok and slot.client:
                    try:
                        await bot.send_message(
                            slot.client.chat_id,
                            "⌛ Время подтверждения записи истекло. Запись автоматически снята. Вы можете выбрать другой слот в меню.",
                            reply_markup=notification_kb(),
                        )
                    except Exception:
                        pass
            except Exception as e:
                logger.exception("Failed to expire pending slot_id=%s: %s", getattr(slot, "id", None), e)

    scheduler.add_job(expire_pending_confirmations, "interval", minutes=1)
    scheduler.start()
    return scheduler