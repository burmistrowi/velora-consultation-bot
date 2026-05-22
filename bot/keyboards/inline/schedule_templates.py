from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def admin_schedule_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 Шаблоны расписания", callback_data="admin_schedule_templates")],
            [InlineKeyboardButton(text="⚙️ Генерация слотов", callback_data="admin_schedule_generate")],
            [InlineKeyboardButton(text="🚫 Исключения", callback_data="admin_schedule_exceptions")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu")],
        ]
    )


def templates_list_kb(templates: list[tuple[int, str]], *, prefix: str) -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton(text=name, callback_data=f"{prefix}:{tid}")] for tid, name in templates]
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_schedule_root")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def templates_manage_kb(template_id: int, *, is_active: bool) -> InlineKeyboardMarkup:
    toggle = "⛔️ Деактивировать" if is_active else "✅ Активировать"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить правило", callback_data=f"admin_tpl_rule_add:{template_id}")],
            [InlineKeyboardButton(text="🧾 Список правил", callback_data=f"admin_tpl_rules:{template_id}")],
            [InlineKeyboardButton(text=toggle, callback_data=f"admin_tpl_toggle:{template_id}")],
            [InlineKeyboardButton(text="🗑 Удалить шаблон", callback_data=f"admin_tpl_delete:{template_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_schedule_templates")],
        ]
    )


def templates_root_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать шаблон", callback_data="admin_tpl_create")],
            [InlineKeyboardButton(text="📄 Открыть шаблон", callback_data="admin_tpl_open")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_schedule_root")],
        ]
    )


def weekdays_kb(*, selected: set[int] | None = None) -> InlineKeyboardMarkup:
    selected = selected or set()
    rows = []
    row = []
    for i, label in enumerate(WEEKDAYS_RU):
        mark = "✅ " if i in selected else ""
        row.append(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"admin_rule_day:{i}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_schedule_templates")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_kb(services: list[tuple[int, str]], *, prefix: str) -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton(text=name, callback_data=f"{prefix}:{sid}")] for sid, name in services]
    keyboard.append([InlineKeyboardButton(text="Без услуги", callback_data=f"{prefix}:0")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_schedule_templates")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def yesno_kb(*, yes_cb: str, no_cb: str, back_cb: str | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="✅ Да", callback_data=yes_cb), InlineKeyboardButton(text="❌ Нет", callback_data=no_cb)]]
    if back_cb:
        rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def weeks_kb() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for w in range(2, 9):
        row.append(InlineKeyboardButton(text=f"{w} нед", callback_data=f"admin_gen_weeks:{w}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_schedule_root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

