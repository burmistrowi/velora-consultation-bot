from __future__ import annotations

from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.admin_calendar import month_picker_kb
from bot.keyboards.inline.common import keyboard
from bot.config import SERVICE_EMOJI


def booking_calendar_kb(*, year: int, month: int, min_date: date, marked_days: set[int]) -> InlineKeyboardMarkup:
    return month_picker_kb(
        year=year,
        month=month,
        min_date=min_date,
        marked_days=marked_days,
        day_callback_prefix="u_book_day:",
        month_callback_prefix="u_book_month:",
        back_callback="back_to_menu",
    )


def booking_times_kb(*, day_iso: str, slot_items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for slot_id, time_label in slot_items:
        rows.append([InlineKeyboardButton(text=f"🕐 {time_label}", callback_data=f"u_book_time:{slot_id}:{day_iso}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu_schedule")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu")])
    return keyboard(rows)


def booking_services_kb(*, slot_id: int, services: list[tuple[int, str]], day_iso: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for sid, name in services:
        rows.append([InlineKeyboardButton(text=f"{SERVICE_EMOJI} {name}", callback_data=f"u_book_service:{sid}:{slot_id}:{day_iso}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"u_book_day:{day_iso}")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu")])
    return keyboard(rows)


def booking_confirm_kb(*, slot_id: int, day_iso: str) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"u_book_confirm:{slot_id}:{day_iso}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu"),
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"u_book_day:{day_iso}")],
        ]
    )


def booking_finalize_confirm_kb(*, slot_id: int) -> InlineKeyboardMarkup:
    """
    Final confirmation after creating a pending appointment.
    """
    return keyboard(
        [
            [InlineKeyboardButton(text="✅ Подтвердить запись", callback_data=f"u_confirm_appointment:{slot_id}")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu")],
        ]
    )

