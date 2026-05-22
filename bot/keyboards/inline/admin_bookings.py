from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.common import keyboard


def bookings_home_kb() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(text="📅 Сегодня", callback_data="admin_bookings_quick:today"),
                InlineKeyboardButton(text="📅 Завтра", callback_data="admin_bookings_quick:tomorrow"),
                InlineKeyboardButton(text="📅 Эта неделя", callback_data="admin_bookings_quick:week"),
            ],
            [InlineKeyboardButton(text="🔍 Поиск по username / ID", callback_data="admin_bookings_search")],
            [
                InlineKeyboardButton(text="✅ Активные", callback_data="admin_bookings_status:active"),
                InlineKeyboardButton(text="⏳ На подтверждении", callback_data="admin_bookings_status:pending_confirmation"),
            ],
            [
                InlineKeyboardButton(text="❌ Отменённые", callback_data="admin_bookings_status:cancelled"),
                InlineKeyboardButton(text="🔁 Перенесённые", callback_data="admin_bookings_status:rescheduled"),
            ],
            [
                InlineKeyboardButton(text="✨ Завершённые", callback_data="admin_bookings_status:completed"),
            ],
            [InlineKeyboardButton(text="📅 Выбрать дату", callback_data="admin_bookings_pick_date")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_bookings")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu")],
        ]
    )


def bookings_list_kb(bookings: list[tuple[int, str]], *, day_iso: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for sid, label in bookings:
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_booking:{sid}:{day_iso}")])
        rows.append(
            [
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"admin_booking_cancel_req:{sid}:{day_iso}"),
                InlineKeyboardButton(text="🔁 Перенести", callback_data=f"admin_booking_move:{sid}:{day_iso}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="📅 Выбрать дату", callback_data="admin_bookings_pick_date")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=f"admin_bookings_day:{day_iso}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back_to_menu")])
    return keyboard(rows)


def booking_details_kb(slot_id: int, *, day_iso: str) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"admin_booking_cancel_req:{slot_id}:{day_iso}"),
                InlineKeyboardButton(text="🔁 Перенести", callback_data=f"admin_booking_move:{slot_id}:{day_iso}"),
            ],
            [InlineKeyboardButton(text="📜 История переносов", callback_data=f"admin_booking_history:{slot_id}:{day_iso}")],
            [InlineKeyboardButton(text="↩️ Откатить перенос", callback_data=f"admin_booking_rollback_req:{slot_id}:{day_iso}")],
            [
                InlineKeyboardButton(text="✨ Завершить", callback_data=f"admin_booking_complete:{slot_id}:{day_iso}"),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_bookings_day:{day_iso}"),
                InlineKeyboardButton(text="◀️ В админ-меню", callback_data="admin_back_to_menu"),
            ],
        ]
    )


def booking_cancel_confirm_kb(slot_id: int, *, day_iso: str) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"admin_booking_cancel_yes:{slot_id}:{day_iso}"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"admin_bookings_day:{day_iso}"),
            ],
            [InlineKeyboardButton(text="◀️ В админ-меню", callback_data="admin_back_to_menu")],
        ]
    )


def booking_move_confirm_kb(old_slot_id: int, new_slot_id: int, *, day_iso: str) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(
                    text="✅ Перенести",
                    callback_data=f"admin_booking_move_yes:{old_slot_id}:{new_slot_id}:{day_iso}",
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_bookings_day:{day_iso}"),
            ],
            [InlineKeyboardButton(text="◀️ В админ-меню", callback_data="admin_back_to_menu")],
        ]
    )


def booking_move_times_kb(*, day_iso: str, slot_items: list[tuple[int, str]], old_slot_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for slot_id, time_label in slot_items:
        rows.append([InlineKeyboardButton(text=f"🕐 {time_label}", callback_data=f"admin_booking_move_time:{old_slot_id}:{slot_id}:{day_iso}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_booking_move_pick_date:{old_slot_id}:{day_iso}")])
    rows.append([InlineKeyboardButton(text="◀️ В админ-меню", callback_data="admin_back_to_menu")])
    return keyboard(rows)

