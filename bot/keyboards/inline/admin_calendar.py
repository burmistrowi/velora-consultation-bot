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


def month_picker_kb(
    *,
    year: int,
    month: int,
    min_date: date,
    marked_days: set[int] | None,
    day_callback_prefix: str,
    month_callback_prefix: str,
    back_callback: str,
) -> InlineKeyboardMarkup:
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)

    rows: list[list[InlineKeyboardButton]] = []
    rows.append([InlineKeyboardButton(text=f"{MONTHS_RU[month]} {year}", callback_data="ignore")])
    rows.append([InlineKeyboardButton(text=wd, callback_data="ignore") for wd in WEEKDAYS])

    marked_days = marked_days or set()
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
            row.append(InlineKeyboardButton(text=f"{d}{dot}", callback_data=f"{day_callback_prefix}{dt.isoformat()}"))
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(text="◀️", callback_data=f"{month_callback_prefix}{year}-{month:02d}:-1"),
            InlineKeyboardButton(text="▶️", callback_data=f"{month_callback_prefix}{year}-{month:02d}:+1"),
        ]
    )
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)])
    return keyboard(rows)

