from __future__ import annotations

from datetime import date, datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import and_

from bot.database.main import Database
from bot.database.models.slot import TimeSlot
from bot.database.methods.create import create_slot
from bot.filters.is_admin import IsAdmin
from bot.keyboards.inline.admin_slots import month_calendar_kb, day_slots_kb, cancel_add_time_kb
from bot.keyboards.inline.admin_slot_service import pick_service_kb
from bot.misc.env import settings
from bot.services.cache import TTLCache
from bot.repositories.services import ServiceRepository
from bot.states.admin import AdminSlotStates
from bot.utils.ui import header, screen, italic, date_human, time_human
from bot.config import SERVICE_EMOJI
from bot.utils.ru_labels import time_slot_status_ru


admin_slots_router = Router()
_month_cache: TTLCache[dict[str, object]] = TTLCache(ttl_seconds=20)


def _month_range(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def _get_month_stats(year: int, month: int) -> tuple[set[int], dict[str, list[TimeSlot]]]:
    key = f"{year}-{month:02d}"

    cached = _month_cache.get(key)
    if cached:
        return cached["marked_days"], cached["by_day"]  # type: ignore[return-value]

    start, end = _month_range(year, month)
    session = Database().session
    try:
        slots = (
            session.query(TimeSlot)
            .filter(and_(TimeSlot.datetime >= start, TimeSlot.datetime < end))
            .order_by(TimeSlot.datetime.asc())
            .all()
        )
    finally:
        session.close()

    by_day: dict[str, list[TimeSlot]] = {}
    marked: set[int] = set()
    for s in slots:
        day_iso = s.datetime.date().isoformat()
        by_day.setdefault(day_iso, []).append(s)
        if s.status == "available" and s.is_available and s.datetime > datetime.now():
            marked.add(s.datetime.day)

    _month_cache.set(key, {"marked_days": marked, "by_day": by_day})
    return marked, by_day


def _slots_menu_text() -> str:
    return screen(header("📅", "Слоты"), ["Выберите дату:"])


def _day_view(day_iso: str) -> tuple[str, object]:
    day = datetime.strptime(day_iso, "%Y-%m-%d").date()
    year, month = day.year, day.month

    _, by_day = _get_month_stats(year, month)
    slots = by_day.get(day_iso, [])
    available_count = sum(1 for s in slots if s.status == "available" and s.is_available and s.datetime > datetime.now())

    lines: list[str] = [
        f"📅 {italic(date_human(datetime(day.year, day.month, day.day)))}",
        f"Свободных слотов: {italic(str(available_count))}",
        "",
    ]

    if not slots:
        lines.append("Слотов на эту дату нет.")
    else:
        for s in slots:
            mark = (
                "🔓"
                if s.status == "available" and s.is_available
                else (
                    "✅"
                    if s.status == "active"
                    else (
                        "⏳"
                        if s.status == "pending_confirmation"
                        else ("🔁" if s.status == "rescheduled" else ("✨" if s.status == "completed" else "❌"))
                    )
                )
            )
            lines.append(f"{mark} 🕐 {time_human(s.datetime)} — {time_slot_status_ru(s.status)}")

    text = screen(header("📅", "Слоты на дату"), lines)
    kb = day_slots_kb(day_iso=day_iso, slots=[(s.id, time_human(s.datetime)) for s in slots])
    return text, kb


async def _render_day(message, day_iso: str) -> None:
    text, kb = _day_view(day_iso)
    await message.edit_text(text, reply_markup=kb)


@admin_slots_router.callback_query(F.data == "admin_slots", IsAdmin())
async def slots_open(callback: CallbackQuery):
    await callback.answer()
    today = date.today()
    marked, _ = _get_month_stats(today.year, today.month)
    await callback.message.edit_text(
        _slots_menu_text(),
        reply_markup=month_calendar_kb(year=today.year, month=today.month, marked_days=marked, min_date=today),
    )


@admin_slots_router.callback_query(F.data.startswith("admin_slots_month:"), IsAdmin())
async def slots_change_month(callback: CallbackQuery):
    await callback.answer()
    payload = callback.data.split(":", 1)[1]  # YYYY-MM:delta
    ym, delta = payload.split(":")
    year_s, month_s = ym.split("-")
    year, month = int(year_s), int(month_s)
    step = -1 if delta == "-1" else 1
    month += step
    if month == 0:
        month = 12
        year -= 1
    elif month == 13:
        month = 1
        year += 1

    today = date.today()
    min_date = today
    marked, _ = _get_month_stats(year, month)
    await callback.message.edit_reply_markup(
        reply_markup=month_calendar_kb(year=year, month=month, marked_days=marked, min_date=min_date),
    )


@admin_slots_router.callback_query(F.data.startswith("admin_slots_day:"), IsAdmin())
async def slots_day(callback: CallbackQuery):
    await callback.answer()
    day_iso = callback.data.split(":", 1)[1]
    await _render_day(callback.message, day_iso)


@admin_slots_router.callback_query(F.data.startswith("admin_slot_addtime:"), IsAdmin())
async def add_time_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    day_iso = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(day_iso=day_iso)
    await state.set_state(AdminSlotStates.waiting_for_time)
    await callback.message.edit_text(
        screen(
            header("➕", "Добавить слот"),
            [
                f"Дата: {italic(day_iso)}",
                "Введите время в формате:",
                italic("HH:MM"),
                "Например: 15:00",
            ],
        ),
        reply_markup=cancel_add_time_kb(day_iso),
    )


@admin_slots_router.message(AdminSlotStates.waiting_for_time, IsAdmin())
async def add_time_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    day_iso = data.get("day_iso")
    if not day_iso:
        await state.clear()
        await message.answer("Сессия устарела. Откройте слоты заново через меню.")
        return

    time_s = (message.text or "").strip()
    try:
        dt = datetime.strptime(f"{day_iso} {time_s}", "%Y-%m-%d %H:%M")
        if dt <= datetime.now():
            await message.answer("Нельзя создавать слот в прошлом. Выберите будущее время.")
            return
    except ValueError:
        await message.answer("Проверьте формат времени. Пример: 15:00")
        return

    await state.update_data(dt=dt.isoformat())
    await state.set_state(AdminSlotStates.waiting_for_service)

    services = ServiceRepository().list(active_only=True)
    await message.answer(
        screen(header("✂️", "Услуга для слота"), ["Выберите услугу (или пропустите):"]),
        reply_markup=pick_service_kb([(s.id, f"{SERVICE_EMOJI} {s.name}") for s in services], day_iso=day_iso),
    )


@admin_slots_router.callback_query(F.data.startswith("admin_slot_pick_service:"), IsAdmin())
async def add_time_pick_service(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    _, service_id_s, day_iso = callback.data.split(":", 2)

    data = await state.get_data()
    dt_iso = data.get("dt")
    if not dt_iso:
        await state.clear()
        await callback.message.edit_text(screen(header("❌", "Ошибка"), ["Сессия устарела. Попробуйте снова."]))
        return

    dt = datetime.fromisoformat(dt_iso)
    service_id = None if service_id_s == "none" else int(service_id_s)
    slot = create_slot(dt, service_id=service_id)

    await state.clear()
    _month_cache.clear()
    await callback.message.edit_text(screen(header("✅", "Слоты"), ["Слот добавлен."]))
    await _render_day(callback.message, day_iso)


@admin_slots_router.callback_query(F.data.startswith("admin_slot_delete:"), IsAdmin())
async def delete_slot(callback: CallbackQuery):
    await callback.answer()
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    slot_id = int(slot_id_s)

    session = Database().session
    try:
        slot = session.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
        if slot:
            session.delete(slot)
            session.commit()
            ok = True
        else:
            ok = False
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    _month_cache.clear()
    await _render_day(callback.message, day_iso)


@admin_slots_router.callback_query(F.data.startswith("admin_slots_clear:"), IsAdmin())
async def clear_day(callback: CallbackQuery):
    await callback.answer()
    day_iso = callback.data.split(":", 1)[1]
    day = datetime.strptime(day_iso, "%Y-%m-%d").date()
    start = datetime(day.year, day.month, day.day)
    end = start + timedelta(days=1)

    session = Database().session
    try:
        session.query(TimeSlot).filter(and_(TimeSlot.datetime >= start, TimeSlot.datetime < end)).delete()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    _month_cache.clear()
    await _render_day(callback.message, day_iso)

