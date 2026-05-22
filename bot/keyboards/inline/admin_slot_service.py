from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.common import keyboard
from bot.config import SERVICE_EMOJI


def pick_service_kb(services: list[tuple[int, str]], *, day_iso: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for sid, name in services:
        # `name` may already include emoji; keep only universal one
        clean = name.replace("✂️", "").strip()
        if clean.startswith(SERVICE_EMOJI):
            label = clean
        else:
            label = f"{SERVICE_EMOJI} {clean}".strip()
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_slot_pick_service:{sid}:{day_iso}")])
    rows.append([InlineKeyboardButton(text="⏭ Без услуги", callback_data=f"admin_slot_pick_service:none:{day_iso}")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_slots_day:{day_iso}")])
    return keyboard(rows)

