from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.common import keyboard


def discounts_list_kb(discount_ids: list[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for did in discount_ids:
        rows.append([InlineKeyboardButton(text=f"💸 Скидка #{did}", callback_data=f"admin_discount:{did}")])
    rows.append([InlineKeyboardButton(text="➕ Создать скидку", callback_data="admin_discount_add")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu")])
    return keyboard(rows)


def discount_actions_kb(discount_id: int) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_discount_edit:{discount_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"admin_discount_delete:{discount_id}")],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_discounts"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu"),
            ],
        ]
    )


def discount_type_kb() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [InlineKeyboardButton(text="На все услуги", callback_data="admin_discount_type:all")],
            [InlineKeyboardButton(text="На выбранные услуги", callback_data="admin_discount_type:selected")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_discounts")],
        ]
    )


def confirm_discount_kb() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(text="✅ Сохранить", callback_data="admin_discount_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_discounts"),
            ]
        ]
    )


def discount_amount_nav_kb() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_discount_amount_back"),
                InlineKeyboardButton(text="🏠 В главное меню", callback_data="admin_discount_amount_menu"),
            ]
        ]
    )

