from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def nav_back(callback_data: str, text: str = "◀️ Назад") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def nav_menu(callback_data: str, text: str = "🏠 Меню") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def row(*buttons: InlineKeyboardButton) -> list[InlineKeyboardButton]:
    return [b for b in buttons if b is not None]


def keyboard(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ignore_button(text: str = " ") -> InlineKeyboardButton:
    # Telegram requires callback_data for all inline buttons.
    return InlineKeyboardButton(text=text, callback_data="ignore")

