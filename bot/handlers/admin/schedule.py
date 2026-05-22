from __future__ import annotations

from datetime import date, datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.admin import get_back_to_admin_menu_keyboard
from bot.keyboards.inline.schedule_templates import (
    WEEKDAYS_RU,
    admin_schedule_menu_kb,
    services_kb,
    templates_list_kb,
    templates_manage_kb,
    templates_root_kb,
    weeks_kb,
    weekdays_kb,
    yesno_kb,
)
from bot.repositories.schedule_templates import ScheduleTemplateRepository
from bot.repositories.services import ServiceRepository
from bot.services.slot_generator import SlotGenerator
from bot.states.admin import AdminScheduleExceptionStates, AdminScheduleGenerateStates, AdminScheduleTemplateStates
from bot.utils.messages import send_auto_delete_message
from bot.keyboards.inline.admin_calendar import month_picker_kb
from bot.middlewares.require_admin import RequireAdminMiddleware


admin_schedule_router = Router()
admin_schedule_router.callback_query.middleware(RequireAdminMiddleware())
admin_schedule_router.message.middleware(RequireAdminMiddleware())


def _parse_hhmm(v: str) -> str | None:
    v = (v or "").strip()
    if not v:
        return None
    if len(v) != 5 or v[2] != ":":
        return None
    hh = v[:2]
    mm = v[3:]
    if not (hh.isdigit() and mm.isdigit()):
        return None
    h = int(hh)
    m = int(mm)
    if h < 0 or h > 23 or m < 0 or m > 59:
        return None
    return f"{hh}:{mm}"


async def _render_template_view(message, *, template_id: int) -> None:
    repo = ScheduleTemplateRepository()
    tpl = repo.get_template(template_id)
    if not tpl:
        await message.edit_text("Шаблон не найден.", reply_markup=templates_root_kb())
        return
    rules = repo.list_rules(template_id)
    rules_text = "\n".join(
        [
            f"- #{r.id} {WEEKDAYS_RU[r.day_of_week]} {r.start_time}-{r.end_time} • {r.slot_duration} мин"
            + (f" • пауза {r.break_minutes} мин" if (getattr(r, 'break_minutes', None) or 0) else "")
            + (f" • перерыв {r.break_start}-{r.break_end}" if r.break_start and r.break_end else "")
            + (f" • услуга {r.service_id}" if r.service_id else "")
            for r in rules
        ]
    )
    if not rules_text:
        rules_text = "_Правил пока нет._"
    await message.edit_text(
        f"📄 Шаблон #{tpl.id} «{tpl.name}»\nСтатус: {'✅ активен' if tpl.is_active else '⛔️ выключен'}\n\n🧾 Правила:\n{rules_text}",
        reply_markup=templates_manage_kb(tpl.id, is_active=tpl.is_active),
    )


async def _render_rules_list(message, *, template_id: int) -> None:
    repo = ScheduleTemplateRepository()
    rules = repo.list_rules(template_id)
    if not rules:
        await message.edit_text("Правил пока нет.", reply_markup=templates_manage_kb(template_id, is_active=True))
        return
    lines = []
    kb_rows = []
    for r in rules:
        lines.append(
            f"- #{r.id} {WEEKDAYS_RU[r.day_of_week]} {r.start_time}-{r.end_time} • {r.slot_duration} мин"
            + (f" • пауза {r.break_minutes} мин" if (getattr(r, 'break_minutes', None) or 0) else "")
            + (f" • перерыв {r.break_start}-{r.break_end}" if r.break_start and r.break_end else "")
            + (f" • услуга {r.service_id}" if r.service_id else "")
        )
        kb_rows.append(
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_rule_edit:{r.id}:{template_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_rule_delete:{r.id}:{template_id}"),
            ]
        )
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_tpl_pick:{template_id}")])
    await message.edit_text("🧾 Правила:\n" + "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


async def _render_exceptions(message) -> None:
    repo = ScheduleTemplateRepository()
    exc = repo.list_exceptions(business_id=1, from_date=date.today())
    lines = []
    kb_rows = []
    for e in exc[:10]:
        if e.exception_type == "off":
            lines.append(f"- #{e.id} 🚫 {e.exception_date} (выходной) {f'— {e.reason}' if e.reason else ''}")
        else:
            lines.append(
                f"- #{e.id} ⭐ {e.exception_date} {e.start_time}-{e.end_time} • {e.slot_duration} мин"
                + (f" • услуга {e.service_id}" if e.service_id else "")
            )
        kb_rows.append([InlineKeyboardButton(text=f"🗑 Удалить #{e.id}", callback_data=f"admin_exc_delete:{e.id}")])
    kb_rows.insert(0, [InlineKeyboardButton(text="➕ Добавить исключение", callback_data="admin_exc_add")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_schedule_root")])
    await message.edit_text(
        "🚫 Исключения\n\n" + ("\n".join(lines) if lines else "_Исключений нет._"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
    )


@admin_schedule_router.callback_query(F.data == "admin_schedule_root")
async def admin_schedule_root(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "📆 Расписание\n\nВыберите раздел:",
        reply_markup=admin_schedule_menu_kb(),
    )
    await cb.answer()


# ---------------- Templates ----------------


@admin_schedule_router.callback_query(F.data == "admin_schedule_templates")
async def admin_schedule_templates(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "📄 Шаблоны расписания\n\nСоздайте шаблон и добавьте правила по дням недели.",
        reply_markup=templates_root_kb(),
    )
    await cb.answer()


@admin_schedule_router.callback_query(F.data == "admin_tpl_create")
async def admin_tpl_create(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminScheduleTemplateStates.waiting_for_template_name)
    await cb.message.edit_text(
        "Введите название шаблона (например: «Будни 10–18»).",
        reply_markup=get_back_to_admin_menu_keyboard(),
    )
    await cb.answer()


@admin_schedule_router.message(AdminScheduleTemplateStates.waiting_for_template_name)
async def admin_tpl_create_name(msg: Message, state: FSMContext):
    name = (msg.text or "").strip()
    if len(name) < 2:
        await send_auto_delete_message(msg.bot, msg.chat.id, "Название слишком короткое. Попробуйте ещё раз.", delay=2)
        return
    repo = ScheduleTemplateRepository()
    tpl_id = repo.create_template(business_id=1, name=name)
    await state.clear()
    await msg.answer(
        f"✅ Шаблон создан: #{tpl_id} «{name}»\n\nТеперь добавьте правила по дням недели.",
        reply_markup=templates_manage_kb(tpl_id, is_active=True),
    )


@admin_schedule_router.callback_query(F.data == "admin_tpl_open")
async def admin_tpl_open(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    repo = ScheduleTemplateRepository()
    tpls = repo.list_templates(business_id=1, active_only=False)
    if not tpls:
        await cb.message.edit_text("Шаблонов пока нет.", reply_markup=templates_root_kb())
        await cb.answer()
        return
    kb = templates_list_kb([(t.id, f"#{t.id} {t.name}{'' if t.is_active else ' (off)'}") for t in tpls], prefix="admin_tpl_pick")
    await cb.message.edit_text("Выберите шаблон:", reply_markup=kb)
    await cb.answer()


@admin_schedule_router.callback_query(F.data.startswith("admin_tpl_pick:"))
async def admin_tpl_pick(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    tpl_id = int(cb.data.split(":")[1])
    await _render_template_view(cb.message, template_id=tpl_id)
    await cb.answer()


@admin_schedule_router.callback_query(F.data.startswith("admin_tpl_toggle:"))
async def admin_tpl_toggle(cb: CallbackQuery, state: FSMContext):
    tpl_id = int(cb.data.split(":")[1])
    repo = ScheduleTemplateRepository()
    tpl = repo.get_template(tpl_id)
    if not tpl:
        await cb.answer("Шаблон не найден", show_alert=True)
        return
    repo.update_template(tpl_id, is_active=not tpl.is_active)
    await cb.answer("Готово")
    await _render_template_view(cb.message, template_id=tpl_id)


@admin_schedule_router.callback_query(F.data.startswith("admin_tpl_delete:"))
async def admin_tpl_delete(cb: CallbackQuery, state: FSMContext):
    tpl_id = int(cb.data.split(":")[1])
    await state.update_data(delete_tpl_id=tpl_id)
    await cb.message.edit_text(
        f"🗑 Удалить шаблон #{tpl_id}?\n\nПравила будут удалены вместе с ним.",
        reply_markup=yesno_kb(yes_cb="admin_tpl_delete_yes", no_cb=f"admin_tpl_pick:{tpl_id}", back_cb="admin_schedule_templates"),
    )
    await cb.answer()


@admin_schedule_router.callback_query(F.data == "admin_tpl_delete_yes")
async def admin_tpl_delete_yes(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tpl_id = int(data.get("delete_tpl_id") or 0)
    repo = ScheduleTemplateRepository()
    ok = repo.delete_template(tpl_id)
    await state.clear()
    await cb.message.edit_text("✅ Удалено." if ok else "Не найдено.", reply_markup=templates_root_kb())
    await cb.answer()


@admin_schedule_router.callback_query(F.data.startswith("admin_tpl_rules:"))
async def admin_tpl_rules(cb: CallbackQuery, state: FSMContext):
    tpl_id = int(cb.data.split(":")[1])
    repo = ScheduleTemplateRepository()
    rules = repo.list_rules(tpl_id)
    if not rules:
        await cb.message.edit_text("Правил пока нет.", reply_markup=templates_manage_kb(tpl_id, is_active=True))
        await cb.answer()
        return
    lines = []
    kb_rows = []
    for r in rules:
        lines.append(
            f"- #{r.id} {WEEKDAYS_RU[r.day_of_week]} {r.start_time}-{r.end_time} • {r.slot_duration} мин"
            + (f" • пауза {r.break_minutes} мин" if (getattr(r, 'break_minutes', None) or 0) else "")
            + (f" • перерыв {r.break_start}-{r.break_end}" if r.break_start and r.break_end else "")
            + (f" • услуга {r.service_id}" if r.service_id else "")
        )
        kb_rows.append(
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_rule_edit:{r.id}:{tpl_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_rule_delete:{r.id}:{tpl_id}"),
            ]
        )
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_tpl_pick:{tpl_id}")])
    await cb.message.edit_text("🧾 Правила:\n" + "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await cb.answer()


@admin_schedule_router.callback_query(F.data.startswith("admin_rule_delete:"))
async def admin_rule_delete(cb: CallbackQuery, state: FSMContext):
    _, rule_id, tpl_id = cb.data.split(":")
    repo = ScheduleTemplateRepository()
    repo.delete_rule(int(rule_id))
    await cb.answer("Удалено")
    await _render_rules_list(cb.message, template_id=int(tpl_id))


@admin_schedule_router.callback_query(F.data.startswith("admin_rule_edit:"))
async def admin_rule_edit(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    _, rule_id_s, tpl_id_s = cb.data.split(":")
    rule_id = int(rule_id_s)
    tpl_id = int(tpl_id_s)
    repo = ScheduleTemplateRepository()
    rule = repo.get_rule(rule_id)
    if not rule:
        await cb.answer("Правило не найдено.", show_alert=True)
        return
    await state.clear()
    await state.update_data(
        rule_template_id=tpl_id,
        edit_rule_id=rule_id,
        edit_mode=True,
        # prefill current values for edit wizard
        cur_day_of_week=int(rule.day_of_week),
        cur_start_time=str(rule.start_time),
        cur_end_time=str(rule.end_time),
        cur_duration=int(rule.slot_duration),
        cur_break_minutes=int(rule.break_minutes or 0),
        cur_service_id=int(rule.service_id) if rule.service_id is not None else 0,
    )
    await state.set_state(AdminScheduleTemplateStates.choosing_rule_day)
    await cb.message.edit_text(
        f"✏️ Редактирование правила #{rule_id}\n\n"
        f"Текущие настройки:\n"
        f"- День: {WEEKDAYS_RU[int(rule.day_of_week)]}\n"
        f"- Время: {rule.start_time}-{rule.end_time}\n"
        f"- Слот: {rule.slot_duration} мин\n"
        f"- Пауза: {int(rule.break_minutes or 0)} мин\n"
        f"- Услуга: {rule.service_id if rule.service_id else '—'}\n\n"
        f"Шаг 1/5. Выберите день недели (или нажмите текущий):",
        reply_markup=weekdays_kb(selected={int(rule.day_of_week)}),
    )


@admin_schedule_router.callback_query(F.data.startswith("admin_tpl_rule_add:"))
async def admin_tpl_rule_add(cb: CallbackQuery, state: FSMContext):
    tpl_id = int(cb.data.split(":")[1])
    await state.update_data(rule_template_id=tpl_id)
    await state.update_data(edit_mode=False, edit_rule_id=None)
    await state.set_state(AdminScheduleTemplateStates.choosing_rule_day)
    await cb.message.edit_text(
        "Выберите день недели для правила:",
        reply_markup=weekdays_kb(),
    )
    await cb.answer()


@admin_schedule_router.callback_query(AdminScheduleTemplateStates.choosing_rule_day, F.data.startswith("admin_rule_day:"))
async def admin_rule_day(cb: CallbackQuery, state: FSMContext):
    dow = int(cb.data.split(":")[1])
    await state.update_data(rule_day_of_week=dow)
    await state.set_state(AdminScheduleTemplateStates.waiting_for_rule_start)
    data = await state.get_data()
    cur = data.get("cur_start_time")
    hint = f"\nТекущее: {cur}\nВведите HH:MM или отправьте «-», чтобы оставить как есть." if cur else "\nВведите HH:MM."
    await cb.message.edit_text(f"День: {WEEKDAYS_RU[dow]}\n\nШаг 2/5. Время начала.{hint}")
    await cb.answer()


@admin_schedule_router.message(AdminScheduleTemplateStates.waiting_for_rule_start)
async def admin_rule_start(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip()
    if raw == "-":
        data = await state.get_data()
        st = data.get("cur_start_time")
        if not st:
            await send_auto_delete_message(msg.bot, msg.chat.id, "Нет текущего значения. Введите время, например 10:00", delay=2)
            return
    else:
        st = _parse_hhmm(raw)
        if not st:
            await send_auto_delete_message(msg.bot, msg.chat.id, "Неверный формат. Пример: 10:00 (или «-» оставить)", delay=2)
            return
    await state.update_data(rule_start_time=st)
    await state.set_state(AdminScheduleTemplateStates.waiting_for_rule_end)
    data = await state.get_data()
    cur = data.get("cur_end_time")
    hint = f"\nТекущее: {cur}\nВведите HH:MM или «-» оставить." if cur else "\nВведите HH:MM."
    await msg.answer(f"Шаг 3/5. Время окончания.{hint}")


@admin_schedule_router.message(AdminScheduleTemplateStates.waiting_for_rule_end)
async def admin_rule_end(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip()
    if raw == "-":
        data = await state.get_data()
        et = data.get("cur_end_time")
        if not et:
            await send_auto_delete_message(msg.bot, msg.chat.id, "Нет текущего значения. Введите время, например 18:00", delay=2)
            return
    else:
        et = _parse_hhmm(raw)
        if not et:
            await send_auto_delete_message(msg.bot, msg.chat.id, "Неверный формат. Пример: 18:00 (или «-» оставить)", delay=2)
            return
    await state.update_data(rule_end_time=et)
    await state.set_state(AdminScheduleTemplateStates.waiting_for_rule_duration)
    data = await state.get_data()
    cur = data.get("cur_duration")
    hint = f"\nТекущее: {cur}\nВведите 30/60 или «-» оставить." if cur else "\nВведите 30 или 60."
    await msg.answer(f"Шаг 4/5. Длительность слота.{hint}")


@admin_schedule_router.message(AdminScheduleTemplateStates.waiting_for_rule_duration)
async def admin_rule_duration(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip()
    if raw == "-":
        data = await state.get_data()
        dur = int(data.get("cur_duration") or 0)
        if dur not in (30, 60):
            await send_auto_delete_message(msg.bot, msg.chat.id, "Нет корректного текущего значения. Введите 30 или 60.", delay=2)
            return
    else:
        try:
            dur = int(raw)
        except ValueError:
            dur = 0
        if dur not in (30, 60):
            await send_auto_delete_message(msg.bot, msg.chat.id, "Разрешено: 30 или 60. Или «-» оставить.", delay=2)
            return
    await state.update_data(rule_duration=dur)
    await state.set_state(AdminScheduleTemplateStates.waiting_for_rule_break)
    data = await state.get_data()
    cur = int(data.get("cur_break_minutes") or 0)
    await msg.answer(
        "Шаг 5/5. Пауза между слотами (в минутах).\n"
        f"Текущее: {cur}\n"
        "Введите число 0–120 или «-», чтобы оставить как есть."
    )


@admin_schedule_router.message(AdminScheduleTemplateStates.waiting_for_rule_break)
async def admin_rule_break(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip().lower()
    # Prefer break in minutes (buffer between slots). Also accept legacy window input HH:MM-HH:MM.
    if raw == "-":
        data = await state.get_data()
        await state.update_data(rule_break_minutes=int(data.get("cur_break_minutes") or 0), rule_break_start=None, rule_break_end=None)
    elif raw in ("нет", "no", "0"):
        await state.update_data(rule_break_minutes=0, rule_break_start=None, rule_break_end=None)
    elif raw.isdigit():
        m = int(raw)
        if m < 0 or m > 120:
            await send_auto_delete_message(msg.bot, msg.chat.id, "Введите число от 0 до 120.", delay=2)
            return
        await state.update_data(rule_break_minutes=m, rule_break_start=None, rule_break_end=None)
    else:
        if "-" not in raw:
            await send_auto_delete_message(msg.bot, msg.chat.id, "Введите число минут (например 10) или 0.", delay=2)
            return
        a, b = raw.split("-", 1)
        bs = _parse_hhmm(a.strip())
        be = _parse_hhmm(b.strip())
        if not bs or not be:
            await send_auto_delete_message(msg.bot, msg.chat.id, "Формат: 13:00-14:00", delay=2)
            return
        await state.update_data(rule_break_minutes=0, rule_break_start=bs, rule_break_end=be)

    services = ServiceRepository().list(active_only=True)
    data = await state.get_data()
    cur_sid = int(data.get("cur_service_id") or 0)
    # Put "keep current" at the top for edit wizard convenience
    items = [(s.id, f"{s.name} ({s.duration_min}м)") for s in services]
    kb_rows: list[list[InlineKeyboardButton]] = []
    if data.get("edit_mode"):
        keep_label = "✅ Оставить текущую" if cur_sid else "✅ Оставить (без услуги)"
        kb_rows.append([InlineKeyboardButton(text=keep_label, callback_data=f"admin_rule_service:{cur_sid}")])
        kb_rows.append([InlineKeyboardButton(text="—", callback_data="ignore")])
    kb = services_kb(items, prefix="admin_rule_service")
    # merge: prepend our rows before kb
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows + kb.inline_keyboard)
    await state.set_state(AdminScheduleTemplateStates.choosing_rule_service)
    await msg.answer("Выберите услугу для правила:", reply_markup=kb)


@admin_schedule_router.callback_query(AdminScheduleTemplateStates.choosing_rule_service, F.data.startswith("admin_rule_service:"))
async def admin_rule_service(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    data = await state.get_data()
    tpl_id = int(data["rule_template_id"])
    edit_mode = bool(data.get("edit_mode"))
    edit_rule_id = int(data.get("edit_rule_id") or 0) if edit_mode else None
    dow = int(data["rule_day_of_week"])
    st = str(data["rule_start_time"])
    et = str(data["rule_end_time"])
    dur = int(data["rule_duration"])
    bmin = int(data.get("rule_break_minutes") or 0)
    bs = data.get("rule_break_start")
    be = data.get("rule_break_end")

    repo = ScheduleTemplateRepository()
    if edit_mode and edit_rule_id:
        ok = repo.update_rule(
            edit_rule_id,
            day_of_week=dow,
            start_time=st,
            end_time=et,
            slot_duration=dur,
            break_minutes=bmin,
            break_start=bs,
            break_end=be,
            service_id=None if sid == 0 else sid,
        )
        if not ok:
            await cb.answer("Не удалось обновить правило.", show_alert=True)
            return
        rule_id = edit_rule_id
        verb = "обновлено"
    else:
        rule_id = repo.add_rule(
            template_id=tpl_id,
            day_of_week=dow,
            start_time=st,
            end_time=et,
            slot_duration=dur,
            break_start=bs,
            break_end=be,
            service_id=None if sid == 0 else sid,
        )
        # break_minutes is optional; keep it via update call for sqlite/postgres compatibility
        repo.update_rule(
            rule_id,
            day_of_week=dow,
            start_time=st,
            end_time=et,
            slot_duration=dur,
            break_minutes=bmin,
            break_start=bs,
            break_end=be,
            service_id=None if sid == 0 else sid,
        )
        verb = "добавлено"
    tpl = repo.get_template(tpl_id)
    await state.clear()
    await cb.message.edit_text(
        f"✅ Правило {verb}: #{rule_id}\n{WEEKDAYS_RU[dow]} {st}-{et} • {dur} мин"
        + (f" • пауза {bmin} мин" if bmin else "")
        + (f" • перерыв {bs}-{be}" if bs and be else "")
        + (f" • услуга {sid}" if sid else ""),
        reply_markup=templates_manage_kb(tpl_id, is_active=bool(tpl.is_active) if tpl else True),
    )
    await cb.answer()


# ---------------- Generation ----------------


@admin_schedule_router.callback_query(F.data == "admin_schedule_generate")
async def admin_schedule_generate(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    repo = ScheduleTemplateRepository()
    tpls = repo.list_templates(business_id=1, active_only=True)
    if not tpls:
        await cb.message.edit_text("Нет активных шаблонов для генерации.", reply_markup=admin_schedule_menu_kb())
        await cb.answer()
        return
    kb = templates_list_kb([(t.id, f"#{t.id} {t.name}") for t in tpls], prefix="admin_gen_tpl")
    await state.set_state(AdminScheduleGenerateStates.choosing_template)
    await cb.message.edit_text("Выберите шаблон для генерации:", reply_markup=kb)
    await cb.answer()


@admin_schedule_router.callback_query(AdminScheduleGenerateStates.choosing_template, F.data.startswith("admin_gen_tpl:"))
async def admin_gen_pick_template(cb: CallbackQuery, state: FSMContext):
    tpl_id = int(cb.data.split(":")[1])
    await state.update_data(gen_template_id=tpl_id)
    await state.set_state(AdminScheduleGenerateStates.choosing_weeks)
    await cb.message.edit_text("На сколько недель вперед сгенерировать?", reply_markup=weeks_kb())
    await cb.answer()


@admin_schedule_router.callback_query(AdminScheduleGenerateStates.choosing_weeks, F.data.startswith("admin_gen_weeks:"))
async def admin_gen_pick_weeks(cb: CallbackQuery, state: FSMContext):
    weeks = int(cb.data.split(":")[1])
    await state.update_data(gen_weeks=weeks)
    await state.set_state(AdminScheduleGenerateStates.choosing_overwrite)
    await cb.message.edit_text(
        "Перегенерировать (удалить ранее сгенерированные доступные слоты этого шаблона в периоде)?",
        reply_markup=yesno_kb(yes_cb="admin_gen_overwrite:1", no_cb="admin_gen_overwrite:0", back_cb="admin_schedule_generate"),
    )
    await cb.answer()


@admin_schedule_router.callback_query(AdminScheduleGenerateStates.choosing_overwrite, F.data.startswith("admin_gen_overwrite:"))
async def admin_gen_run(cb: CallbackQuery, state: FSMContext):
    overwrite = cb.data.split(":")[1] == "1"
    data = await state.get_data()
    tpl_id = int(data["gen_template_id"])
    weeks = int(data["gen_weeks"])

    repo = ScheduleTemplateRepository()
    rules = repo.list_rules(tpl_id)
    if not rules:
        await cb.message.edit_text(
            "⚠️ В шаблоне нет правил.\n\n"
            "Сначала добавьте хотя бы одно правило (день недели → время → длительность → услуга), "
            "и только потом запускайте генерацию.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📄 Открыть шаблон", callback_data=f"admin_tpl_pick:{tpl_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_schedule_generate")],
                ]
            ),
        )
        await cb.answer()
        return

    await state.update_data(gen_overwrite=overwrite)
    await state.set_state(AdminScheduleGenerateStates.choosing_overwrite)

    gen = SlotGenerator()
    preview = gen.preview_slots_from_template(template_id=tpl_id, start_date=date.today(), weeks_ahead=weeks, max_examples=3)
    examples = []
    for ex in preview.examples:
        dt_s = ex.dt.strftime("%d.%m %H:%M")
        examples.append(f"- {dt_s}" + (f" • услуга {ex.service_id}" if ex.service_id else ""))
    ex_text = "\n".join(examples) if examples else "—"

    await cb.message.edit_text(
        "📌 Предпросмотр генерации\n\n"
        f"Будет создано примерно {preview.estimated_total} слотов\n"
        f"на период с {preview.from_date.isoformat()} по {(preview.to_date_exclusive.isoformat())}\n\n"
        f"Примеры:\n{ex_text}\n\n"
        "Запустить генерацию?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Сгенерировать", callback_data="admin_gen_do")],
                [InlineKeyboardButton(text="🧪 Тест на 1 неделю", callback_data="admin_gen_test_1w")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_schedule_generate")],
            ]
        ),
    )
    await cb.answer()


@admin_schedule_router.callback_query(F.data == "admin_gen_do")
async def admin_gen_do(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    tpl_id = int(data["gen_template_id"])
    weeks = int(data["gen_weeks"])
    overwrite = bool(data.get("gen_overwrite"))
    await state.clear()

    gen = SlotGenerator()
    res = gen.generate_slots_from_template(template_id=tpl_id, start_date=date.today(), weeks_ahead=weeks, overwrite=overwrite)
    await cb.message.edit_text(
        "✅ Генерация завершена.\n\n"
        f"- Создано: {res.created}\n"
        f"- Пропущено (уже было): {res.skipped_existing}\n"
        f"- Удалено при overwrite: {res.deleted_overwritten}\n",
        reply_markup=admin_schedule_menu_kb(),
    )


@admin_schedule_router.callback_query(F.data == "admin_gen_test_1w")
async def admin_gen_test_1w(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    tpl_id = int(data["gen_template_id"])
    overwrite = bool(data.get("gen_overwrite"))
    await state.clear()
    gen = SlotGenerator()
    res = gen.generate_slots_from_template(template_id=tpl_id, start_date=date.today(), weeks_ahead=1, overwrite=overwrite)
    await cb.message.edit_text(
        "🧪 Тестовая генерация (1 неделя) завершена.\n\n"
        f"- Создано: {res.created}\n"
        f"- Пропущено (уже было): {res.skipped_existing}\n"
        f"- Удалено при overwrite: {res.deleted_overwritten}\n",
        reply_markup=admin_schedule_menu_kb(),
    )


# ---------------- Exceptions ----------------


@admin_schedule_router.callback_query(F.data == "admin_schedule_exceptions")
async def admin_schedule_exceptions(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await _render_exceptions(cb.message)
    await cb.answer()


@admin_schedule_router.callback_query(F.data.startswith("admin_exc_delete:"))
async def admin_exc_delete(cb: CallbackQuery, state: FSMContext):
    exc_id = int(cb.data.split(":")[1])
    ScheduleTemplateRepository().delete_exception(exc_id)
    await cb.answer("Удалено")
    await _render_exceptions(cb.message)


@admin_schedule_router.callback_query(F.data == "admin_exc_add")
async def admin_exc_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminScheduleExceptionStates.choosing_exception_type)
    await cb.message.edit_text(
        "Какое исключение добавить?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚫 Выходной день", callback_data="admin_exc_type:off")],
                [InlineKeyboardButton(text="⭐ Особое расписание", callback_data="admin_exc_type:special")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_schedule_exceptions")],
            ]
        ),
    )
    await cb.answer()


@admin_schedule_router.callback_query(AdminScheduleExceptionStates.choosing_exception_type, F.data.startswith("admin_exc_type:"))
async def admin_exc_type(cb: CallbackQuery, state: FSMContext):
    t = cb.data.split(":")[1]
    await state.update_data(exc_type=t)
    today = date.today()
    await state.set_state(AdminScheduleExceptionStates.waiting_for_exception_date)
    await cb.message.edit_text(
        "Выберите дату исключения:",
        reply_markup=month_picker_kb(
            year=today.year,
            month=today.month,
            min_date=today,
            marked_days=None,
            day_callback_prefix="admin_exc_day:",
            month_callback_prefix="admin_exc_month:",
            back_callback="admin_schedule_exceptions",
        ),
    )
    await cb.answer()

@admin_schedule_router.callback_query(AdminScheduleExceptionStates.waiting_for_exception_date, F.data.startswith("admin_exc_month:"))
async def admin_exc_change_month(cb: CallbackQuery):
    await cb.answer()
    payload = cb.data.split(":", 1)[1]
    ym, delta = payload.split(":")
    y, m = ym.split("-")
    year, month = int(y), int(m)
    step = -1 if delta == "-1" else 1
    month += step
    if month == 0:
        month = 12
        year -= 1
    elif month == 13:
        month = 1
        year += 1
    today = date.today()
    await cb.message.edit_reply_markup(
        reply_markup=month_picker_kb(
            year=year,
            month=month,
            min_date=today,
            marked_days=None,
            day_callback_prefix="admin_exc_day:",
            month_callback_prefix="admin_exc_month:",
            back_callback="admin_schedule_exceptions",
        )
    )


@admin_schedule_router.callback_query(AdminScheduleExceptionStates.waiting_for_exception_date, F.data.startswith("admin_exc_day:"))
async def admin_exc_pick_day(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    exc_date = cb.data.split(":", 1)[1]
    await state.update_data(exc_date=exc_date)
    data = await state.get_data()
    if data.get("exc_type") == "off":
        await state.set_state(AdminScheduleExceptionStates.waiting_for_exception_reason)
        await cb.message.edit_text(
            f"🚫 Выходной: {exc_date}\n\nПричина (необязательно). Напишите текст или «-».",
        )
        return
    await state.set_state(AdminScheduleExceptionStates.waiting_for_exception_window)
    await cb.message.edit_text(
        f"⭐ Особое расписание: {exc_date}\n\nОкно работы (HH:MM-HH:MM).",
    )


@admin_schedule_router.message(AdminScheduleExceptionStates.waiting_for_exception_window)
async def admin_exc_window(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip()
    if "-" not in raw:
        await send_auto_delete_message(msg.bot, msg.chat.id, "Формат: 10:00-16:00", delay=2)
        return
    a, b = raw.split("-", 1)
    st = _parse_hhmm(a.strip())
    et = _parse_hhmm(b.strip())
    if not st or not et:
        await send_auto_delete_message(msg.bot, msg.chat.id, "Формат: 10:00-16:00", delay=2)
        return
    await state.update_data(exc_start=st, exc_end=et)
    await state.set_state(AdminScheduleExceptionStates.waiting_for_exception_duration)
    await msg.answer("Длительность слота (30 или 60).")


@admin_schedule_router.message(AdminScheduleExceptionStates.waiting_for_exception_duration)
async def admin_exc_duration(msg: Message, state: FSMContext):
    try:
        dur = int((msg.text or "").strip())
    except ValueError:
        dur = 0
    if dur not in (30, 60):
        await send_auto_delete_message(msg.bot, msg.chat.id, "Разрешено: 30 или 60.", delay=2)
        return
    await state.update_data(exc_duration=dur)
    services = ServiceRepository().list(active_only=True)
    kb = services_kb([(s.id, f"{s.name} ({s.duration_min}м)") for s in services], prefix="admin_exc_service")
    await state.set_state(AdminScheduleExceptionStates.choosing_exception_service)
    await msg.answer("Выберите услугу:", reply_markup=kb)


@admin_schedule_router.callback_query(AdminScheduleExceptionStates.choosing_exception_service, F.data.startswith("admin_exc_service:"))
async def admin_exc_service(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    await state.update_data(exc_service_id=None if sid == 0 else sid)
    await state.set_state(AdminScheduleExceptionStates.waiting_for_exception_reason)
    await cb.message.edit_text("Причина (необязательно). Напишите текст или «-».")
    await cb.answer()


@admin_schedule_router.message(AdminScheduleExceptionStates.waiting_for_exception_reason)
async def admin_exc_reason(msg: Message, state: FSMContext):
    reason = (msg.text or "").strip()
    if reason == "-" or reason.lower() == "нет":
        reason = None
    data = await state.get_data()
    repo = ScheduleTemplateRepository()
    exc_type = data.get("exc_type")
    exc_date = data.get("exc_date")
    if exc_type == "off":
        repo.add_exception(
            business_id=1,
            exception_date=exc_date,
            exception_type="off",
            start_time=None,
            end_time=None,
            slot_duration=None,
            service_id=None,
            reason=reason,
        )
    else:
        repo.add_exception(
            business_id=1,
            exception_date=exc_date,
            exception_type="special",
            start_time=data.get("exc_start"),
            end_time=data.get("exc_end"),
            slot_duration=int(data.get("exc_duration") or 60),
            service_id=data.get("exc_service_id"),
            reason=reason,
        )
    await state.clear()
    await msg.answer("✅ Исключение добавлено.", reply_markup=admin_schedule_menu_kb())

