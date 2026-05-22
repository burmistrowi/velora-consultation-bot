from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.common import keyboard
from bot.config import SERVICE_EMOJI


def services_list_kb(service_items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for sid, label in service_items:
        rows.append([InlineKeyboardButton(text=f"{SERVICE_EMOJI} {label}", callback_data=f"admin_service:{sid}")])
    rows.append([InlineKeyboardButton(text="➕ Добавить услугу", callback_data="admin_service_add")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu")])
    return keyboard(rows)


def service_actions_kb(service_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_service_edit:{service_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"admin_service_delete:{service_id}"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_services"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu"),
        ],
    ]
    return keyboard(rows)


def confirm_save_service_kb(action: str, service_id: int | None = None) -> InlineKeyboardMarkup:
    suffix = f":{service_id}" if service_id is not None else ""
    rows = [
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data=f"admin_service_confirm:{action}{suffix}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin_services"),
        ],
    ]
    return keyboard(rows)

