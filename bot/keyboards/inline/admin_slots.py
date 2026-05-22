from __future__ import annotations

import calendar
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.common import keyboard, ignore_button


WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS_RU = [
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]


def month_calendar_kb(
    *,
    year: int,
    month: int,
    marked_days: set[int],
    min_date: date,
) -> InlineKeyboardMarkup:
    cal = calendar.Calendar(firstweekday=0)  # Monday
    month_days = cal.monthdayscalendar(year, month)

    rows: list[list[InlineKeyboardButton]] = []

    rows.append([InlineKeyboardButton(text=f"{MONTHS_RU[month]} {year}", callback_data="ignore")])
    rows.append([InlineKeyboardButton(text=wd, callback_data="ignore") for wd in WEEKDAYS])

    for week in month_days:
        row: list[InlineKeyboardButton] = []
        for d in week:
            if d == 0:
                row.append(ignore_button(" "))
                continue

            dt = date(year, month, d)
            if dt < min_date:
                row.append(ignore_button("·"))
                continue

            dot = "🟢" if d in marked_days else ""
            row.append(InlineKeyboardButton(text=f"{d}{dot}", callback_data=f"admin_slots_day:{dt.isoformat()}"))
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(text="◀️", callback_data=f"admin_slots_month:{year}-{month:02d}:-1"),
            InlineKeyboardButton(text="▶️", callback_data=f"admin_slots_month:{year}-{month:02d}:+1"),
        ]
    )
    rows.append([InlineKeyboardButton(text="📆 Расписание (шаблоны)", callback_data="admin_schedule_root")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu")])
    return keyboard(rows)


def day_slots_kb(*, day_iso: str, slots: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for sid, time_label in slots:
        rows.append(
            [InlineKeyboardButton(text=f"🕐 {time_label} | ❌", callback_data=f"admin_slot_delete:{sid}:{day_iso}")]
        )

    rows.append([InlineKeyboardButton(text="➕ Добавить время", callback_data=f"admin_slot_addtime:{day_iso}")])
    rows.append([InlineKeyboardButton(text="🗑 Очистить все", callback_data=f"admin_slots_clear:{day_iso}")])
    rows.append([InlineKeyboardButton(text="📆 Расписание (шаблоны)", callback_data="admin_schedule_root")])
    rows.append(
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_slots"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu"),
        ]
    )
    return keyboard(rows)


def cancel_add_time_kb(day_iso: str) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_slots_day:{day_iso}")],
        ]
    )

