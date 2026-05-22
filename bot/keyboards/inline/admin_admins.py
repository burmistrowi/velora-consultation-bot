from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.common import keyboard


def admins_list_kb(admin_ids: list[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for aid in admin_ids:
        rows.append([InlineKeyboardButton(text=f"👤 Админ #{aid}", callback_data=f"admin_admin:{aid}")])
    rows.append([InlineKeyboardButton(text="➕ Добавить администратора", callback_data="admin_admin_add")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu")])
    return keyboard(rows)


def admin_actions_kb(admin_id: int) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"admin_admin_delete:{admin_id}")],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_admins"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu"),
            ],
        ]
    )


def confirm_add_admin_kb(username: str) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(text="✅ Добавить", callback_data=f"admin_admin_confirm_add:{username}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_admins"),
            ]
        ]
    )

