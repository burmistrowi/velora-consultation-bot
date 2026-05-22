from __future__ import annotations

from datetime import date, datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import logging

from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from bot.database.methods.read import get_slot_by_id
from bot.database.methods.read import get_available_slots
from bot.database.methods.update import book_slot, release_slot, reschedule_booking, atomic_reschedule
from bot.database.main import Database
from bot.database.models.slot import TimeSlot
from bot.database.models.user import User
from bot.filters.is_admin import IsAdmin
from bot.keyboards.inline.admin_bookings import (
    bookings_home_kb,
    bookings_list_kb,
    booking_details_kb,
    booking_cancel_confirm_kb,
    booking_move_times_kb,
    booking_move_confirm_kb,
)
from bot.keyboards.inline.admin_calendar import month_picker_kb
from bot.repositories.bookings import BookingRepository
from bot.repositories.reschedules import RescheduleRepository
from bot.repositories.services import ServiceRepository
from bot.utils.ui import header, screen, italic, dt_human
from bot.config import SERVICE_EMOJI
from bot.states.admin import AdminBookingMoveStates
from bot.states.admin import AdminBookingsSearchStates
from bot.utils.messages import send_auto_delete_message
from bot.utils.formatters import format_appointments_compact
from bot.utils.ru_labels import booking_slot_status_caption


admin_bookings_router = Router()
logger = logging.getLogger(__name__)


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_move_pick_date:"), IsAdmin())
async def booking_move_pick_date(callback: CallbackQuery, state: FSMContext):
    """
    Back button from time picker to calendar.
    admin_booking_move_pick_date:<old_slot_id>:<origin_day_iso>
    """
    await callback.answer()
    logger.info("booking_move_pick_date data=%s", callback.data)
    _, old_slot_id_s, origin_day_iso = callback.data.split(":", 2)
    old_slot_id = int(old_slot_id_s)

    await state.set_state(AdminBookingMoveStates.choosing_date)
    await state.update_data(old_slot_id=old_slot_id, origin_day_iso=origin_day_iso)

    today = date.today()
    await _safe_edit(
        callback.message,
        screen(header("🔁", "Перенос записи"), ["Выберите новую дату:"]),
        reply_markup=month_picker_kb(
            year=today.year,
            month=today.month,
            min_date=today,
            marked_days=None,
            day_callback_prefix=f"admin_booking_move_day:{old_slot_id}:",
            month_callback_prefix=f"admin_booking_move_month:{old_slot_id}:",
            back_callback=f"admin_bookings_day:{origin_day_iso}",
        ),
    )

async def _safe_edit(message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        # Ignore "message is not modified" to prevent crashes on repeated clicks
        from aiogram.exceptions import TelegramBadRequest

        if isinstance(e, TelegramBadRequest) and "message is not modified" in str(e).lower():
            return
        raise


async def _render_bookings_day(message, day_iso: str, *, status: str = "active") -> None:
    day = datetime.strptime(day_iso, "%Y-%m-%d").date()
    repo = BookingRepository()
    bookings = repo.list_booked_for_day(datetime(day.year, day.month, day.day), status=status)
    services = {s.id: s for s in ServiceRepository().list(active_only=False)}

    items: list[dict] = []
    total = 0
    for s in bookings:
        meta = repo.get_meta(s.id)
        is_conf = bool(meta and meta.is_confirmed)
        if s.status == "active":
            total += 1
        service_id = meta.booked_service_id if meta and meta.booked_service_id else getattr(s, "service_id", None)
        svc = services.get(service_id) if service_id else None
        svc_name = svc.name if svc else "Консультация"
        duration = int(getattr(svc, "duration_min", 60)) if svc else 60
        end_dt = s.datetime + timedelta(minutes=duration)
        tr = f"{s.datetime.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"

        client = f"@{s.client.username}" if s.client and s.client.username else (f"ID {s.client.chat_id}" if s.client else "—")
        st = "✅" if (s.status == "active" and is_conf) else "⏳"
        items.append({"client": client, "service_name": svc_name, "time_range": tr, "status_emoji": st})

    text = format_appointments_compact(day, items=items, total=total)

    await _safe_edit(
        message,
        text,
        reply_markup=bookings_list_kb(
            [(b.id, f"🕐 {b.datetime.strftime('%H:%M')} · 👤 @{b.client.username}" if b.client and b.client.username else f"🕐 {b.datetime.strftime('%H:%M')} · 👤 ID {b.client.chat_id if b.client else '—'}")
             for b in bookings],
            day_iso=day_iso,
        ),
    )

async def _render_bookings_week(message, start_day: date, *, status: str = "active") -> None:
    """
    Renders bookings for a 7-day window starting from start_day.
    """
    session = Database().session
    try:
        start_dt = datetime(start_day.year, start_day.month, start_day.day)
        end_dt = start_dt + timedelta(days=7)
        rows = (
            session.query(TimeSlot)
            .options(joinedload(TimeSlot.client))
            .filter(
                and_(
                    TimeSlot.datetime >= start_dt,
                    TimeSlot.datetime < end_dt,
                    TimeSlot.status == status,
                )
            )
            .order_by(TimeSlot.datetime.asc())
            .all()
        )
    finally:
        session.close()

    if not rows:
        await _safe_edit(
            message,
            screen(header("📋", "Записи (неделя)"), ["Записей не найдено."]),
            reply_markup=bookings_home_kb(),
        )
        return

    # Group by day for readability
    lines: list[str] = []
    services = {s.id: s for s in ServiceRepository().list(active_only=False)}
    for b in rows:
        d = b.datetime.strftime("%d.%m.%Y")
        if not lines or not lines[-1].startswith(f"📅 {d}"):
            if lines:
                lines.append("")
            lines.append(f"📅 {d}")
        meta = BookingRepository().get_meta(b.id)
        service_id = meta.booked_service_id if meta and meta.booked_service_id else getattr(b, "service_id", None)
        svc = services.get(service_id) if service_id else None
        svc_name = svc.name if svc else "Консультация"
        client = f"@{b.client.username}" if b.client and b.client.username else (f"ID {b.client.chat_id}" if b.client else "—")
        lines.append(f"• 🕐 {b.datetime.strftime('%H:%M')} · 👤 {client} · {svc_name}")

    await _safe_edit(
        message,
        screen(header("📋", "Записи (неделя)"), lines),
        reply_markup=bookings_home_kb(),
    )


async def _render_search_results(message, *, slots: list[TimeSlot]) -> None:
    if not slots:
        await _safe_edit(
            message,
            screen(header("🔍", "Поиск"), ["Ничего не найдено."]),
            reply_markup=bookings_home_kb(),
        )
        return

    rows: list[list[InlineKeyboardButton]] = []
    for s in slots[:20]:
        day_iso = s.datetime.date().isoformat()
        client_id = s.client.chat_id if s.client else None
        label = f"🕐 {s.datetime.strftime('%d.%m %H:%M')} · 👤 @{s.client.username}" if s.client and s.client.username else f"🕐 {s.datetime.strftime('%d.%m %H:%M')} · 👤 ID {client_id or '—'}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_booking:{s.id}:{day_iso}")])
        action_row = [InlineKeyboardButton(text="❌ Отменить", callback_data=f"admin_booking_cancel_req:{s.id}:{day_iso}")]
        if client_id:
            action_row.append(InlineKeyboardButton(text="💬 Чат", url=f"tg://user?id={client_id}"))
        rows.append(action_row)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_bookings")])
    await _safe_edit(
        message,
        screen(header("🔍", "Результаты поиска"), [f"Найдено: {len(slots)} (показано до 20)"]),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@admin_bookings_router.callback_query(F.data == "admin_bookings", IsAdmin())
async def bookings_home(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await _safe_edit(
        callback.message,
        screen(header("📋", "Записи"), ["Выберите фильтр или откройте дату:"]),
        reply_markup=bookings_home_kb(),
    )


@admin_bookings_router.callback_query(F.data.startswith("admin_bookings_quick:"), IsAdmin())
async def bookings_quick(callback: CallbackQuery):
    await callback.answer()
    key = callback.data.split(":", 1)[1]
    today = date.today()
    if key == "today":
        await _render_bookings_day(callback.message, today.isoformat(), status="active")
        return
    if key == "tomorrow":
        d = today + timedelta(days=1)
        await _render_bookings_day(callback.message, d.isoformat(), status="active")
        return
    if key == "week":
        await _render_bookings_week(callback.message, today, status="active")
        return
    await callback.answer("Неизвестный фильтр", show_alert=True)


@admin_bookings_router.callback_query(F.data == "admin_bookings_search", IsAdmin())
async def bookings_search_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(AdminBookingsSearchStates.waiting_for_query)
    await _safe_edit(
        callback.message,
        screen(header("🔍", "Поиск"), ["Введите username (без @) или Telegram ID:"]),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_bookings")]]
        ),
    )


@admin_bookings_router.message(AdminBookingsSearchStates.waiting_for_query, IsAdmin())
async def bookings_search_query(message: Message, state: FSMContext):
    q = (message.text or "").strip()
    await state.clear()
    if not q:
        await send_auto_delete_message(message.bot, message.chat.id, "Введите запрос текстом.", delay=2)
        return

    # Normalize: allow @username
    if q.startswith("@"):
        q = q[1:]

    session = Database().session
    try:
        qs = (
            session.query(TimeSlot)
            .options(joinedload(TimeSlot.client))
            .join(User, TimeSlot.client_id == User.id)
            .filter(TimeSlot.status.in_(["active", "pending_confirmation"]))
        )
        if q.isdigit():
            cid = int(q)
            qs = qs.filter(User.chat_id == cid)
        else:
            qs = qs.filter(User.username == q)
        # limit to upcoming 90 days to keep output relevant
        now = datetime.now()
        qs = qs.filter(TimeSlot.datetime >= now, TimeSlot.datetime < (now + timedelta(days=90))).order_by(TimeSlot.datetime.asc())
        slots = qs.all()
    finally:
        session.close()

    await _render_search_results(message, slots=slots)


@admin_bookings_router.callback_query(F.data.startswith("admin_bookings_status:"), IsAdmin())
async def bookings_today_by_status(callback: CallbackQuery):
    await callback.answer()
    status = callback.data.split(":", 1)[1]
    today_iso = date.today().isoformat()
    await _render_bookings_day(callback.message, today_iso, status=status)


@admin_bookings_router.callback_query(F.data == "admin_bookings_pick_date", IsAdmin())
async def bookings_pick_date(callback: CallbackQuery):
    await callback.answer()
    today = date.today()
    await _safe_edit(
        callback.message,
        screen(header("📅", "Выбор даты"), ["Выберите дату для просмотра записей:"]),
        reply_markup=month_picker_kb(
            year=today.year,
            month=today.month,
            min_date=today,
            marked_days=None,
            day_callback_prefix="admin_bookings_day:",
            month_callback_prefix="admin_bookings_month:",
            back_callback="admin_bookings",
        ),
    )


@admin_bookings_router.callback_query(F.data.startswith("admin_bookings_month:"), IsAdmin())
async def bookings_change_month(callback: CallbackQuery):
    await callback.answer()
    payload = callback.data.split(":", 1)[1]
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
    await callback.message.edit_reply_markup(
        reply_markup=month_picker_kb(
            year=year,
            month=month,
            min_date=today,
            marked_days=None,
            day_callback_prefix="admin_bookings_day:",
            month_callback_prefix="admin_bookings_month:",
            back_callback="admin_bookings",
        )
    )


@admin_bookings_router.callback_query(F.data.startswith("admin_bookings_day:"), IsAdmin())
async def bookings_for_day(callback: CallbackQuery):
    await callback.answer()
    day_iso = callback.data.split(":", 1)[1]
    await _render_bookings_day(callback.message, day_iso, status="active")


@admin_bookings_router.callback_query(F.data.startswith("admin_booking:"), IsAdmin())
async def booking_details(callback: CallbackQuery):
    await callback.answer()
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    slot_id = int(slot_id_s)
    slot = get_slot_by_id(slot_id)
    repo = BookingRepository()
    meta = repo.ensure_meta(slot_id)
    services_map = {s.id: s.name for s in ServiceRepository().list(active_only=False)}
    service_id = meta.booked_service_id if meta and meta.booked_service_id else (getattr(slot, "service_id", None) if slot else None)
    service_name = services_map.get(service_id) if service_id else "Консультация"

    if not slot:
        await callback.message.edit_text(screen(header("📋", "Записи"), ["Запись не найдена."]))
        return

    client = f"@{slot.client.username}" if slot.client and slot.client.username else "—"
    lines = [
        f"👤 {client}",
        f"{SERVICE_EMOJI} {italic(service_name)}",
        f"🕐 {italic(dt_human(slot.datetime))}",
        f"Статус: {booking_slot_status_caption(slot, meta)}",
    ]
    await callback.message.edit_text(
        screen(header("📋", "Детали записи"), lines),
        reply_markup=booking_details_kb(slot_id, day_iso=day_iso),
    )


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_confirm:"), IsAdmin())
async def booking_confirm(callback: CallbackQuery):
    await callback.answer()
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    slot_id = int(slot_id_s)
    BookingRepository().set_confirmed(slot_id, confirmed=True)
    await _render_bookings_day(callback.message, day_iso)


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_complete:"), IsAdmin())
async def booking_complete(callback: CallbackQuery):
    await callback.answer()
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    slot_id = int(slot_id_s)
    BookingRepository().set_completed(slot_id, completed=True)
    await _render_bookings_day(callback.message, day_iso)


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_cancel_req:"), IsAdmin())
async def booking_cancel_request(callback: CallbackQuery):
    await callback.answer()
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    slot_id = int(slot_id_s)
    slot = get_slot_by_id(slot_id)
    if not slot or slot.status not in ("active", "pending_confirmation"):
        await _safe_edit(callback.message, "Запись не найдена.", reply_markup=None)
        return
    await _safe_edit(
        callback.message,
        screen(header("❌", "Отмена записи"), [f"Отменить запись на {italic(dt_human(slot.datetime))}?", "Подтвердите действие:"]),
        reply_markup=booking_cancel_confirm_kb(slot_id, day_iso=day_iso),
    )


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_cancel_yes:"), IsAdmin())
async def booking_cancel_yes(callback: CallbackQuery):
    await callback.answer()
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    slot_id = int(slot_id_s)
    slot = get_slot_by_id(slot_id)
    if not slot or slot.status not in ("active", "pending_confirmation") or not slot.client:
        await _render_bookings_day(callback.message, day_iso)
        return

    client_chat_id = slot.client.chat_id
    ok = release_slot(slot_id)
    if ok:
        try:
            await send_auto_delete_message(
                callback.bot,
                client_chat_id,
                f"❌ Ваша запись на {slot.datetime.strftime('%d.%m.%Y %H:%M')} была отменена администратором.",
                delay=2,
            )
        except Exception:
            pass
    await _render_bookings_day(callback.message, day_iso)


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_move:"), IsAdmin())
async def booking_move_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    logger.info("booking_move_start data=%s from=%s", callback.data, callback.from_user.id if callback.from_user else None)
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    old_slot_id = int(slot_id_s)
    old_slot = get_slot_by_id(old_slot_id)
    if not old_slot or old_slot.status not in ("active", "pending_confirmation"):
        logger.warning("booking_move_start slot not booked slot_id=%s", old_slot_id)
        await _render_bookings_day(callback.message, day_iso)
        return

    await state.clear()
    await state.set_state(AdminBookingMoveStates.choosing_date)
    await state.update_data(old_slot_id=old_slot_id, origin_day_iso=day_iso)

    today = date.today()
    await _safe_edit(
        callback.message,
        screen(header("🔁", "Перенос записи"), ["Выберите новую дату:"]),
        reply_markup=month_picker_kb(
            year=today.year,
            month=today.month,
            min_date=today,
            marked_days=None,
            day_callback_prefix=f"admin_booking_move_day:{old_slot_id}:",
            month_callback_prefix=f"admin_booking_move_month:{old_slot_id}:",
            back_callback=f"admin_bookings_day:{day_iso}",
        ),
    )


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_move_month:"), IsAdmin())
async def booking_move_month(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    logger.info("booking_move_month data=%s", callback.data)
    # admin_booking_move_month:<old_slot_id>:YYYY-MM:delta
    _, rest = callback.data.split("admin_booking_move_month:", 1)
    old_slot_id_s, payload = rest.split(":", 1)
    old_slot_id = int(old_slot_id_s)
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

    data = await state.get_data()
    origin_day_iso = data.get("origin_day_iso") or date.today().isoformat()
    today = date.today()
    await callback.message.edit_reply_markup(
        reply_markup=month_picker_kb(
            year=year,
            month=month,
            min_date=today,
            marked_days=None,
            day_callback_prefix=f"admin_booking_move_day:{old_slot_id}:",
            month_callback_prefix=f"admin_booking_move_month:{old_slot_id}:",
            back_callback=f"admin_bookings_day:{origin_day_iso}",
        )
    )


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_move_day:"), IsAdmin())
async def booking_move_day(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    logger.info("booking_move_day data=%s", callback.data)
    # admin_booking_move_day:<old_slot_id>:YYYY-MM-DD
    _, rest = callback.data.split("admin_booking_move_day:", 1)
    old_slot_id_s, day_iso = rest.split(":", 1)
    old_slot_id = int(old_slot_id_s)
    day = datetime.strptime(day_iso, "%Y-%m-%d").date()
    start = datetime(day.year, day.month, day.day)
    end = start + timedelta(days=1)
    slots = get_available_slots(start, end)

    await state.set_state(AdminBookingMoveStates.choosing_time)
    await state.update_data(old_slot_id=old_slot_id, target_day_iso=day_iso)

    items = [(s.id, s.datetime.strftime("%H:%M")) for s in slots]
    await _safe_edit(
        callback.message,
        screen(header("🔁", "Перенос записи"), [f"Дата: {italic(day.strftime('%d.%m.%Y'))}", "Выберите новое время:"]),
        reply_markup=booking_move_times_kb(day_iso=day_iso, slot_items=items, old_slot_id=old_slot_id),
    )


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_move_time:"), IsAdmin())
async def booking_move_time(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    logger.info("booking_move_time data=%s", callback.data)
    # admin_booking_move_time:<old_slot_id>:<new_slot_id>:<day_iso>
    _, old_slot_id_s, new_slot_id_s, day_iso = callback.data.split(":", 3)
    old_slot_id = int(old_slot_id_s)
    new_slot_id = int(new_slot_id_s)

    old_slot = get_slot_by_id(old_slot_id)
    new_slot = get_slot_by_id(new_slot_id)
    if not old_slot or not new_slot or new_slot.status != "available" or not new_slot.is_available:
        await _render_bookings_day(callback.message, day_iso)
        return

    await state.set_state(AdminBookingMoveStates.confirming)
    await state.update_data(old_slot_id=old_slot_id, new_slot_id=new_slot_id, target_day_iso=day_iso)

    await _safe_edit(
        callback.message,
        screen(
            header("🔁", "Подтверждение переноса"),
            [
                f"Старая дата: {italic(dt_human(old_slot.datetime))}",
                f"Новая дата: {italic(dt_human(new_slot.datetime))}",
                "",
                "Перенести запись?",
            ],
        ),
        reply_markup=booking_move_confirm_kb(old_slot_id, new_slot_id, day_iso=day_iso),
    )


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_move_yes:"), IsAdmin())
async def booking_move_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    current_state = await state.get_state()
    state_data = await state.get_data()
    logger.info(
        "booking_move_yes data=%s fsm_state=%s fsm_data=%s",
        callback.data,
        current_state,
        state_data,
    )
    # admin_booking_move_yes:<old_slot_id>:<new_slot_id>:<day_iso>
    try:
        _, old_slot_id_s, new_slot_id_s, day_iso = callback.data.split(":", 3)
        old_slot_id = int(old_slot_id_s)
        new_slot_id = int(new_slot_id_s)
    except Exception as e:
        logger.exception("booking_move_yes parse error: %s", e)
        await callback.answer("Ошибка данных кнопки. См. логи.", show_alert=True)
        return

    # Sanity-check against FSM (helps debug mismatched callback/state)
    if state_data:
        if int(state_data.get("old_slot_id") or old_slot_id) != old_slot_id:
            logger.warning("booking_move_yes mismatch old_slot_id callback=%s state=%s", old_slot_id, state_data.get("old_slot_id"))
        if int(state_data.get("new_slot_id") or new_slot_id) != new_slot_id:
            logger.warning("booking_move_yes mismatch new_slot_id callback=%s state=%s", new_slot_id, state_data.get("new_slot_id"))

    try:
        old_slot = get_slot_by_id(old_slot_id)
        new_slot = get_slot_by_id(new_slot_id)
        if not old_slot or not old_slot.client or not new_slot:
            await state.clear()
            await _render_bookings_day(callback.message, day_iso)
            return

        user_id = old_slot.client_id
        client_chat_id = old_slot.client.chat_id
        old_dt = old_slot.datetime
        new_dt = new_slot.datetime

        meta = BookingRepository().get_meta(old_slot_id)
        service_id = (meta.booked_service_id if meta and meta.booked_service_id else getattr(old_slot, "service_id", None))
        service = ServiceRepository().get(service_id) if service_id else None
        service_name = service.name if service else "Консультация"

        ok = atomic_reschedule(
            business_id=getattr(old_slot, "business_id", 1),
            old_slot_id=old_slot_id,
            new_slot_id=new_slot_id,
            created_by=(callback.from_user.id if callback.from_user else 0),
        )
        if not ok:
            await callback.answer("Новый слот уже занят.", show_alert=True)
            await state.clear()
            await _render_bookings_day(callback.message, day_iso)
            return

        # keep existing non-critical history table (optional)
        RescheduleRepository().add(old_slot_id=old_slot_id, new_slot_id=new_slot_id, actor_chat_id=(callback.from_user.id if callback.from_user else None))

        client_text = (
            "🔁 Ваша запись перенесена администратором.\n\n"
            f"🕐 Было: {old_dt.strftime('%d.%m.%Y %H:%M')}\n"
            f"🕐 Стало: {new_dt.strftime('%d.%m.%Y %H:%M')}\n"
            f"{SERVICE_EMOJI} Услуга: {service_name}"
        )
        try:
            await send_auto_delete_message(callback.bot, client_chat_id, client_text, delay=2)
        except Exception as e:
            logger.exception("booking_move_yes failed to notify client chat_id=%s: %s", client_chat_id, e)

        # Notify admin (current operator)
        try:
            await send_auto_delete_message(callback.bot, callback.from_user.id, f"✅ Перенос выполнен.\n\n{client_text}", delay=2)
        except Exception:
            pass

    except Exception as e:
        logger.exception("booking_move_yes failed: %s", e)
        await callback.answer("Ошибка при переносе. См. логи.", show_alert=True)
        return

    await state.clear()
    await _render_bookings_day(callback.message, day_iso)


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_history:"), IsAdmin())
async def booking_history(callback: CallbackQuery):
    await callback.answer()
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    slot_id = int(slot_id_s)
    slot = get_slot_by_id(slot_id)
    if not slot:
        await _render_bookings_day(callback.message, day_iso)
        return

    rows = RescheduleRepository().list_for_slot(slot_id=slot_id)
    lines: list[str] = [f"📜 {header('🔁', 'История переносов')}", f"Слот: {italic(dt_human(slot.datetime))}", ""]
    if not rows:
        lines.append("Переносов не найдено.")
    else:
        for r in rows[:10]:
            rb = " (откат)" if r.get("rolled_back") else ""
            lines.append(f"#{r.get('id')} {r.get('old_slot_id')} → {r.get('new_slot_id')}{rb}")
    await callback.message.edit_text(
        screen(header("📜", "История переносов"), lines),
        reply_markup=booking_details_kb(slot_id, day_iso=day_iso),
    )


@admin_bookings_router.callback_query(F.data.startswith("admin_booking_rollback_req:"), IsAdmin())
async def booking_rollback(callback: CallbackQuery):
    await callback.answer()
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    slot_id = int(slot_id_s)

    rr = RescheduleRepository()
    rec = rr.last_for_new(new_slot_id=slot_id)
    if not rec or rec.get("rolled_back"):
        await callback.answer("Нет переноса для отката.", show_alert=True)
        await _render_bookings_day(callback.message, day_iso)
        return

    old_slot_id = int(rec["old_slot_id"])
    new_slot_id = int(rec["new_slot_id"])
    old_slot = get_slot_by_id(old_slot_id)
    new_slot = get_slot_by_id(new_slot_id)
    if not old_slot or not new_slot or not new_slot.client:
        await callback.answer("Не удалось откатить (записи не найдены).", show_alert=True)
        await _render_bookings_day(callback.message, day_iso)
        return

    user_id = new_slot.client_id
    client_chat_id = new_slot.client.chat_id

    # Reactivate old slot (keep history)
    session = Database().session
    try:
        os = session.query(TimeSlot).filter(TimeSlot.id == old_slot_id).first()
        ns = session.query(TimeSlot).filter(TimeSlot.id == new_slot_id).first()
        if not os or not ns:
            raise RuntimeError("slots not found in session")

        # Old becomes active
        os.status = "active"
        os.is_available = False
        os.client_id = user_id
        os.is_confirmed = True
        os.confirmed_at = datetime.utcnow()
        os.confirmation_deadline = None

        # New becomes rescheduled + clone available at its datetime
        ns.status = "rescheduled"
        ns.is_available = False
        ns.confirmation_deadline = None

        new_free = TimeSlot(
            datetime=ns.datetime,
            is_available=True,
            client_id=None,
            status="available",
            currency=ns.currency,
            service_id=getattr(ns, "service_id", None),
            is_confirmed=False,
            confirmed_at=None,
            confirmation_deadline=None,
        )
        session.add(new_free)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception("rollback failed: %s", e)
        await callback.answer("Ошибка отката. См. логи.", show_alert=True)
        return
    finally:
        session.close()

    BookingRepository().move_meta(new_slot_id, old_slot_id)
    rr.mark_rolled_back(reschedule_id=int(rec["id"]))

    try:
        await callback.bot.send_message(
            client_chat_id,
            "↩️ Администратор откатил перенос. Ваша запись возвращена на исходное время.",
        )
    except Exception:
        pass

    await _render_bookings_day(callback.message, day_iso)

