"""Русские подписи для раздела записи и связанных экранов."""

from __future__ import annotations

# Частые англоязычные названия услуг в шаблонах / тестовых БД → отображение для пользователя
_SERVICE_NAME_ALIASES: dict[str, str] = {
    "consultation": "Консультация",
    "default": "Консультация",
    "default service": "Консультация",
    "therapy": "Терапия",
    "therapy session": "Сеанс терапии",
    "session": "Сеанс",
    "standard consultation": "Стандартная консультация",
    "online consultation": "Онлайн-консультация",
}


def service_display_name(name: str | None) -> str:
    """Возвращает название услуги для показа пользователю (русские эквиваленты для типовых англ. имён)."""
    if not name or not str(name).strip():
        return "Консультация"
    raw = str(name).strip()
    mapped = _SERVICE_NAME_ALIASES.get(raw.casefold())
    return mapped if mapped else raw


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 11 <= n_abs <= 19:
        return many
    if n1 == 1:
        return one
    if 2 <= n1 <= 4:
        return few
    return many


def humanize_minutes_until(total_minutes: int) -> str:
    m = max(1, int(total_minutes))
    w = plural_ru(m, "минуту", "минуты", "минут")
    return f"через {m} {w}"


def humanize_hours_until(hours: int) -> str:
    h = max(1, int(hours))
    w = plural_ru(h, "час", "часа", "часов")
    return f"через {h} {w}"


def time_slot_status_ru(status: str | None) -> str:
    """Русская подпись статуса слота/записи (как в БД: active, pending_confirmation, …)."""
    if not status or not str(status).strip():
        return "Неизвестно"
    key = str(status).strip().casefold()
    return {
        "available": "Свободен",
        "active": "Активна",
        "pending_confirmation": "Ожидает подтверждения",
        "cancelled": "Отменена",
        "rescheduled": "Перенесена",
        "completed": "Завершена",
    }.get(key, str(status))


def booking_slot_status_caption(slot, meta=None) -> str:
    """
    Статус для карточки записи в админке: эмодзи + краткая русская подпись.
    `slot` — объект TimeSlot или с полем .status; `meta` — booking_meta или None.
    """
    if not slot:
        return "—"
    st = (getattr(slot, "status", None) or "").strip()
    if st == "cancelled":
        return f"❌ {time_slot_status_ru('cancelled')}"
    if st == "rescheduled":
        return f"🔁 {time_slot_status_ru('rescheduled')}"
    if meta is not None and getattr(meta, "is_completed", False):
        return f"✨ {time_slot_status_ru('completed')}"
    if st == "pending_confirmation":
        return f"⏳ {time_slot_status_ru('pending_confirmation')}"
    if st == "active":
        confirmed = bool(getattr(meta, "is_confirmed", False)) if meta is not None else False
        if not confirmed:
            confirmed = bool(getattr(slot, "is_confirmed", False))
        if confirmed:
            return "✅ Подтверждена"
        return f"✅ {time_slot_status_ru('active')}"
    if st == "completed":
        return f"✨ {time_slot_status_ru('completed')}"
    if st == "available":
        avail = bool(getattr(slot, "is_available", True))
        return f"🔓 {time_slot_status_ru('available')}" if avail else f"• {time_slot_status_ru('available')}"
    return f"• {time_slot_status_ru(st)}"
