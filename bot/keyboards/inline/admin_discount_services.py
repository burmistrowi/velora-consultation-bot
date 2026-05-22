from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.common import keyboard


def discount_services_pick_kb(
    services: list[tuple[int, str]],
    *,
    selected: set[int],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for sid, name in services:
        mark = "✅" if sid in selected else "☑️"
        rows.append([InlineKeyboardButton(text=f"{mark} {name}", callback_data=f"admin_discount_srv_toggle:{sid}")])
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="admin_discount_srv_done")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_discount_add")])
    return keyboard(rows)

