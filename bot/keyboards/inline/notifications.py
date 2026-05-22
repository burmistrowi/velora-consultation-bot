from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.common import keyboard


def notification_kb() -> InlineKeyboardMarkup:
    """
    Unified keyboard for bot notifications:
    - OK: acknowledge
    - Ask admin: opens support flow
    - Main menu: go to menu
    """
    return keyboard(
        [
            [InlineKeyboardButton(text="👌 Ок", callback_data="notif_ok")],
            [InlineKeyboardButton(text="💬 Задать вопрос администратору", callback_data="menu_support")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
        ]
    )


def admin_notification_kb() -> InlineKeyboardMarkup:
    """
    Notifications for admins should not include "write to admin" actions.
    """
    return keyboard(
        [
            [InlineKeyboardButton(text="👌 Ок", callback_data="notif_ok")],
            [InlineKeyboardButton(text="🏠 Админ-меню", callback_data="admin_back_to_menu")],
        ]
    )

