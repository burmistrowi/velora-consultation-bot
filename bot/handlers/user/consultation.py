from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta, date

from bot.database.methods.read import get_available_slots, get_slot_by_id, get_user_upcoming_appointments, check_user_booking_limit, get_user_by_chat_id
from bot.keyboards.inline.booking import (
    booking_calendar_kb,
    booking_times_kb,
    booking_services_kb,
    booking_confirm_kb,
    booking_finalize_confirm_kb,
)
from bot.keyboards.inline.consultation import (
    create_bookings_keyboard,
    create_booking_details_keyboard,
    get_no_bookings_keyboard,
    get_success_booking_keyboard,
)
from bot.keyboards.reply.phone import phone_request_keyboard, remove_reply_keyboard
from bot.misc.env import settings
from bot.middlewares.throttling import AdminMessageThrottlingMiddleware
from bot.states.consultation import ConsultationStates, BookingFlowStates, RescheduleStates
from bot.repositories.bookings import BookingRepository
from bot.repositories.services import ServiceRepository
from bot.repositories.support import SupportRepository
from bot.services.notifications import notify_admins_booking_cancelled, notify_admins_booking_created
from bot.keyboards.inline.menu import get_back_to_menu_keyboard
from bot.config import SERVICE_EMOJI
from bot.utils.messages import send_auto_delete_message
from bot.utils.formatters import format_appointments_compact
from bot.utils.ru_labels import humanize_hours_until, humanize_minutes_until, service_display_name
from bot.database.methods.update import atomic_reschedule, book_slot, release_slot
from bot.keyboards.inline.admin_calendar import month_picker_kb

consultation_router = Router()
consultation_router.message.middleware(AdminMessageThrottlingMiddleware(cooldown_minutes=30))


def _user_owns_slot(slot, user) -> bool:
    if not slot or not user or slot.client_id is None:
        return False
    return int(slot.client_id) == int(user.id)

async def show_schedule(message: Message, edit: bool = False):
    today = date.today()
    from_date = datetime.now()
    to_date = from_date + timedelta(days=30)
    slots = get_available_slots(from_date, to_date)

    if not slots:
        text = "К сожалению, нет доступных слотов для записи."
        if edit:
            await message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
        else:
            await message.answer(text, reply_markup=get_back_to_menu_keyboard())
        return

    marked_days = {s.datetime.day for s in slots if s.datetime.month == today.month and s.datetime.year == today.year}
    text = "📅 Выберите свободную дату:"
    if edit:
        await message.edit_text(text, reply_markup=booking_calendar_kb(year=today.year, month=today.month, min_date=today, marked_days=marked_days))
    else:
        await message.answer(text, reply_markup=booking_calendar_kb(year=today.year, month=today.month, min_date=today, marked_days=marked_days))

@consultation_router.callback_query(F.data.startswith("u_book_month:"))
async def booking_change_month(callback: CallbackQuery):
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
    from_date = datetime.now()
    to_date = from_date + timedelta(days=60)
    slots = get_available_slots(from_date, to_date)
    marked_days = {s.datetime.day for s in slots if s.datetime.month == month and s.datetime.year == year}
    await callback.message.edit_reply_markup(
        reply_markup=booking_calendar_kb(year=year, month=month, min_date=today, marked_days=marked_days)
    )

@consultation_router.callback_query(F.data.startswith("u_book_day:"))
async def booking_pick_day(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    day_iso = callback.data.split(":", 1)[1]
    day = datetime.strptime(day_iso, "%Y-%m-%d").date()
    start = datetime(day.year, day.month, day.day)
    end = start + timedelta(days=1)
    slots = get_available_slots(start, end)

    await state.clear()
    await state.set_state(BookingFlowStates.choosing_time)
    await state.update_data(day_iso=day_iso)

    times = [(s.id, s.datetime.strftime("%H:%M")) for s in slots]
    await callback.message.edit_text(
        f"🕐 Выберите свободное время на {day.strftime('%d.%m.%Y')}:",
        reply_markup=booking_times_kb(day_iso=day_iso, slot_items=times),
    )

@consultation_router.callback_query(F.data.startswith("u_book_time:"))
async def booking_pick_time(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    slot_id = int(slot_id_s)
    slot = get_slot_by_id(slot_id)
    if not slot or slot.status != "available" or not slot.is_available:
        await callback.message.edit_text("❌ Этот слот уже недоступен. Выберите другой.")
        return

    await state.update_data(slot_id=slot_id, day_iso=day_iso)
    await state.set_state(BookingFlowStates.choosing_service)

    services_repo = ServiceRepository()
    if getattr(slot, "service_id", None):
        s = services_repo.get(slot.service_id)
        services = [(s.id, service_display_name(s.name))] if s else []
    else:
        services = [(s.id, service_display_name(s.name)) for s in services_repo.list(active_only=True)]

    await callback.message.edit_text(
        f"{SERVICE_EMOJI} Выберите услугу:",
        reply_markup=booking_services_kb(slot_id=slot_id, services=services, day_iso=day_iso),
    )


@consultation_router.callback_query(F.data.startswith("u_book_service:"), StateFilter(BookingFlowStates.choosing_service))
async def booking_pick_service(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    _, service_id_s, slot_id_s, day_iso = callback.data.split(":", 3)
    service_id = int(service_id_s)
    slot_id = int(slot_id_s)

    await state.update_data(service_id=service_id, slot_id=slot_id, day_iso=day_iso)
    await state.set_state(BookingFlowStates.waiting_for_name)
    await callback.message.edit_text("👤 Введите ваше имя:")


@consultation_router.message(StateFilter(BookingFlowStates.waiting_for_name))
async def booking_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Введите имя текстом.")
        return
    await state.update_data(client_name=name)
    await state.set_state(BookingFlowStates.waiting_for_phone)
    await message.answer("📱 Отправьте номер телефона:", reply_markup=phone_request_keyboard())


@consultation_router.message(StateFilter(BookingFlowStates.waiting_for_phone))
async def booking_phone(message: Message, state: FSMContext):
    phone = None
    if message.contact and message.contact.phone_number:
        phone = message.contact.phone_number
    else:
        raw = (message.text or "").strip()
        digits = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
        if len(digits) < 8:
            await message.answer("Введите корректный номер телефона или нажмите кнопку отправки контакта.")
            return
        phone = digits

    await state.update_data(client_phone=phone)
    await state.set_state(BookingFlowStates.waiting_for_confirm)

    data = await state.get_data()
    slot = get_slot_by_id(int(data["slot_id"]))
    service = ServiceRepository().get(int(data["service_id"]))
    summary = (
        f"✅ Подтверждение записи\n\n"
        f"📅 Дата: {slot.datetime.strftime('%d.%m.%Y')}\n"
        f"🕐 Время: {slot.datetime.strftime('%H:%M')}\n"
        f"{SERVICE_EMOJI} Услуга: {service_display_name(service.name if service else None)}\n"
        f"👤 Имя: {data.get('client_name')}\n"
        f"📱 Телефон: {data.get('client_phone')}\n"
    )
    await message.answer(summary, reply_markup=remove_reply_keyboard())
    await message.answer("Подтвердить?", reply_markup=booking_confirm_kb(slot_id=int(data["slot_id"]), day_iso=data["day_iso"]))


@consultation_router.callback_query(F.data.startswith("u_book_confirm:"), StateFilter(BookingFlowStates.waiting_for_confirm))
async def booking_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    slot_id = int(data["slot_id"])
    user = get_user_by_chat_id(callback.from_user.id)
    slot = get_slot_by_id(slot_id)
    if not user or not slot:
        await state.clear()
        await callback.message.edit_text("❌ Ошибка. Попробуйте снова через меню.")
        return

    if not check_user_booking_limit(user.id, settings.BOOKING_LIMIT):
        await callback.message.edit_text(
            f"❌ Достигнут лимит записей ({settings.BOOKING_LIMIT} активных и ожидающих подтверждения). "
            "Отмените лишние или дождитесь завершения."
        )
        return

    # Create appointment in pending_confirmation with 15-minute deadline
    deadline = datetime.now() + timedelta(minutes=15)
    if book_slot(slot_id, user.id, status="pending_confirmation", confirmation_deadline=deadline):
        BookingRepository().set_client_info(
            slot_id,
            name=data.get("client_name"),
            phone=data.get("client_phone"),
            booked_service_id=int(data.get("service_id")) if data.get("service_id") else None,
        )
        await state.clear()
        await callback.message.edit_text("⏳ Запись создана и ожидает подтверждения.", reply_markup=get_success_booking_keyboard())
        client_label = f"@{callback.from_user.username}" if callback.from_user.username else f"пользователь {callback.from_user.id}"
        await notify_admins_booking_created(callback.bot, slot.datetime, client_label)
        await callback.message.answer(
            "✅ Чтобы запись стала активной, подтвердите её в течение 15 минут.",
            reply_markup=booking_finalize_confirm_kb(slot_id=slot_id),
        )
    else:
        await callback.message.edit_text("❌ Слот уже занят. Выберите другой.")


@consultation_router.callback_query(F.data.startswith("u_confirm_appointment:"))
async def confirm_appointment(callback: CallbackQuery):
    await callback.answer()
    _, slot_id_s = callback.data.split(":", 1)
    slot_id = int(slot_id_s)

    slot = get_slot_by_id(slot_id)
    if not slot or not slot.client:
        await callback.message.edit_text("❌ Запись не найдена.")
        return

    # Only owner can confirm
    if callback.from_user.id != slot.client.chat_id:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    if slot.status != "pending_confirmation":
        if slot.status == "active":
            await callback.message.edit_text("✅ Запись уже подтверждена.")
        else:
            await callback.message.edit_text("❌ Эту запись нельзя подтвердить (статус изменился).")
        return

    if slot.confirmation_deadline and datetime.now() > slot.confirmation_deadline:
        await callback.message.edit_text("⌛ Время подтверждения истекло. Запись снята.")
        return

    BookingRepository().set_confirmed(slot_id, confirmed=True)
    # Short-lived success notification
    await send_auto_delete_message(callback.bot, callback.from_user.id, "✅ Запись подтверждена.", delay=2)
    # Auto-refresh: show updated bookings list
    await show_my_bookings(callback.message, edit=True)

async def show_my_bookings(message: Message, edit: bool = False):
    user = get_user_by_chat_id(message.chat.id)
    if not user:
        text = "❌ Произошла ошибка. Попробуйте начать сначала с /start"
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return
        
    bookings = get_user_upcoming_appointments(user.id)
    active_bookings = len([b for b in bookings if b.status == "active"])
    pending_bookings = len([b for b in bookings if b.status == "pending_confirmation"])
    
    if not bookings:
        text = (f"У вас нет предстоящих консультаций.\n"
                f"Доступно записей: {settings.BOOKING_LIMIT}")
        keyboard = get_no_bookings_keyboard()
        if edit:
            await message.edit_text(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)
        return
    
    keyboard = await create_bookings_keyboard(bookings, page=1)

    # Compact formatted list grouped by day
    services = {s.id: s for s in ServiceRepository().list(active_only=False)}
    by_day: dict[date, list[dict]] = {}
    active_by_day: dict[date, int] = {}
    for s in bookings:
        meta = BookingRepository().get_meta(s.id)
        is_conf = bool(meta and meta.is_confirmed)
        service_id = meta.booked_service_id if meta and meta.booked_service_id else getattr(s, "service_id", None)
        svc = services.get(service_id) if service_id else None
        svc_name = service_display_name(svc.name if svc else None)
        duration = int(getattr(svc, "duration_min", 60)) if svc else 60
        end_dt = s.datetime + timedelta(minutes=duration)
        tr = f"{s.datetime.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
        client = f"@{message.from_user.username}" if message.from_user.username else f"пользователь {user.chat_id}"
        st = "✅" if (s.status == "active" and is_conf) else "⏳"
        d = s.datetime.date()
        by_day.setdefault(d, []).append({"client": client, "service_name": svc_name, "time_range": tr, "status_emoji": st})
        if s.status == "active":
            active_by_day[d] = active_by_day.get(d, 0) + 1

    parts: list[str] = []
    # show up to first 5 days to keep message compact
    for d in sorted(by_day.keys())[:5]:
        parts.append(format_appointments_compact(d, items=by_day[d], total=active_by_day.get(d, 0)))
        parts.append("")  # spacer

    text = "\n".join(parts).strip()
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)

@consultation_router.callback_query(F.data.startswith("booking_details_"))
async def show_booking_details(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[2])
    slot = get_slot_by_id(booking_id)
    meta = BookingRepository().get_meta(booking_id)
    
    if not slot:
        await callback.answer("Консультация не найдена")
        return

    user = get_user_by_chat_id(callback.from_user.id)
    if not user or not _user_owns_slot(slot, user):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
        
    time_until = slot.datetime - datetime.now()
    hours_left = int(time_until.total_seconds() / 3600)
    
    if hours_left < 1:
        time_info = humanize_minutes_until(int(time_until.total_seconds() / 60))
    else:
        time_info = humanize_hours_until(hours_left)
    
    pending_info = ""
    show_confirm = False
    if slot.status == "pending_confirmation":
        show_confirm = True
        if slot.confirmation_deadline:
            seconds_left = int((slot.confirmation_deadline - datetime.now()).total_seconds())
            if seconds_left <= 0:
                pending_info = "\n⌛ Подтверждение просрочено — запись будет снята автоматически."
            else:
                mins_left = max(1, seconds_left // 60)
                pending_info = f"\n⏳ Ожидает подтверждения. Осталось: {mins_left} мин."

    keyboard = await create_booking_details_keyboard(booking_id, show_confirm=show_confirm)
    service_id = meta.booked_service_id if meta and meta.booked_service_id else getattr(slot, "service_id", None)
    service = ServiceRepository().get(service_id) if service_id else None
    await callback.message.edit_text(
        f"📅 Консультация {slot.datetime.strftime('%d.%m.%Y %H:%M')}\n"
        f"{SERVICE_EMOJI} Услуга: {service_display_name(service.name if service else None)}\n"
        f"⏳ Начнется {time_info}{pending_info}\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@consultation_router.callback_query(F.data.startswith("cancel_booking_"))
async def process_booking_cancellation(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[2])
    user = get_user_by_chat_id(callback.from_user.id)
    slot = get_slot_by_id(booking_id)
    
    if not slot:
        await callback.answer("❌ Запись не найдена")
        return

    if not user or not _user_owns_slot(slot, user):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
        
    client_info = f"@{user.username}" if user.username else f"пользователь {user.chat_id}"
    time_until = slot.datetime - datetime.now()
    
    success = release_slot(booking_id)
    
    if success:
        refund_message = ""
        
        await notify_admins_booking_cancelled(callback.bot, slot.datetime, client_info)
        # Short-lived success notification for client
        await send_auto_delete_message(callback.bot, callback.from_user.id, "✅ Запись отменена.", delay=2)
        
        bookings = get_user_upcoming_appointments(user.id)
        if bookings:
            keyboard = await create_bookings_keyboard(bookings, page=1)
            await callback.message.edit_text(
                f"✅ Запись отменена{refund_message}\n\n"
                f"📅 Ваши предстоящие консультации (активные: {len([b for b in bookings if b.status == 'active'])}/{settings.BOOKING_LIMIT}):",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(
                f"✅ Запись отменена{refund_message}\n\n"
                f"У вас нет предстоящих консультаций.\n"
                f"Доступно записей: {settings.BOOKING_LIMIT}",
                reply_markup=get_no_bookings_keyboard(),
            )
    else:
        await callback.message.edit_text("❌ Не удалось отменить запись", reply_markup=get_back_to_menu_keyboard())

@consultation_router.callback_query(F.data == "back_to_bookings")
async def back_to_bookings_list(callback: CallbackQuery):
    user = get_user_by_chat_id(callback.from_user.id)
    if not user:
        await callback.answer("Сначала нажмите /start.", show_alert=True)
        return
    bookings = get_user_upcoming_appointments(user.id)
    keyboard = await create_bookings_keyboard(bookings, page=1)
    
    await callback.message.edit_text(
        f"📅 Ваши предстоящие консультации (активные: {len([b for b in bookings if b.status == 'active'])}/{settings.BOOKING_LIMIT}):",
        reply_markup=keyboard
    )

@consultation_router.callback_query(F.data.startswith("bookings_page_"))
async def process_bookings_page(callback: CallbackQuery):
    page = int(callback.data.split("_")[2])
    user = get_user_by_chat_id(callback.from_user.id)
    if not user:
        await callback.answer("Сначала нажмите /start.", show_alert=True)
        return
    bookings = get_user_upcoming_appointments(user.id)
    
    keyboard = await create_bookings_keyboard(bookings, page=page)
    await callback.message.edit_reply_markup(reply_markup=keyboard) 

@consultation_router.callback_query(F.data.startswith("cancel_"))
async def cancel_booking_creation(callback: CallbackQuery):
    await callback.answer()
    await show_schedule(callback.message, edit=True)

@consultation_router.callback_query(F.data.startswith("write_admin_"))
async def process_write_admin(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split("_")[2])
    slot = get_slot_by_id(booking_id)
    
    if not slot:
        await callback.answer("Консультация не найдена")
        return

    user = get_user_by_chat_id(callback.from_user.id)
    if not user or not _user_owns_slot(slot, user):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
        
    await state.update_data(booking_id=booking_id)
    await state.set_state(ConsultationStates.waiting_for_message)
    
    await callback.message.edit_text(
        "📝 Пожалуйста, напишите ваше сообщение для администратора.\n"
        "Оно будет отправлено вместе с информацией о вашей консультации."
    )

@consultation_router.message(StateFilter(ConsultationStates.waiting_for_message))
async def process_admin_message(message: Message, state: FSMContext):
    data = await state.get_data()
    booking_id = data.get("booking_id")
    slot = get_slot_by_id(booking_id)
    
    if not slot:
        await message.answer("❌ Произошла ошибка. Консультация не найдена.")
        await state.clear()
        return

    user_row = get_user_by_chat_id(message.from_user.id)
    if not user_row or not _user_owns_slot(slot, user_row):
        await message.answer("❌ Недостаточно прав для этой записи.")
        await state.clear()
        return
        
    user_message = (message.text or "").strip()
    if not user_message:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return
    user = message.from_user
    client_info = f"{user.first_name}"
    if user.last_name:
        client_info += f" {user.last_name}"
    if user.username:
        client_info += f" (@{user.username})"
    
    # Save to support system (badge only in admin panel)
    SupportRepository().create_client_message(
        business_id=SupportRepository.DEFAULT_BUSINESS_ID,
        client_id=message.from_user.id,
        client_username=message.from_user.username,
        message=f"📅 Слот: {slot.datetime.strftime('%d.%m.%Y %H:%M')}\n📝 {user_message}",
    )
    
    await message.answer("✅ Сообщение отправлено. Администратор ответит вам в этом чате.")
    await state.clear()
    
    show_confirm = slot.status == "pending_confirmation" if slot else False
    keyboard = await create_booking_details_keyboard(booking_id, show_confirm=show_confirm)
    await message.answer(
        f"📅 Консультация {slot.datetime.strftime('%d.%m.%Y %H:%M')}\n"
        "Выберите действие:",
        reply_markup=keyboard
    ) 


@consultation_router.callback_query(F.data.startswith("u_reschedule_start:"))
async def user_reschedule_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    old_slot_id = int(callback.data.split(":", 1)[1])
    slot = get_slot_by_id(old_slot_id)
    if not slot or not slot.client or callback.from_user.id != slot.client.chat_id:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    await state.clear()
    await state.set_state(RescheduleStates.choosing_date)
    await state.update_data(old_slot_id=old_slot_id)

    today = date.today()
    await callback.message.edit_text(
        "🔄 Перенос записи\n\nВыберите новую дату:",
        reply_markup=month_picker_kb(
            year=today.year,
            month=today.month,
            min_date=today,
            marked_days=None,
            day_callback_prefix=f"u_reschedule_day:{old_slot_id}:",
            month_callback_prefix=f"u_reschedule_month:{old_slot_id}:",
            back_callback="menu_bookings",
        ),
    )


@consultation_router.callback_query(F.data.startswith("u_reschedule_month:"))
async def user_reschedule_month(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    # u_reschedule_month:<old_slot_id>:YYYY-MM:delta
    _, rest = callback.data.split("u_reschedule_month:", 1)
    old_slot_id_s, payload = rest.split(":", 1)
    old_slot_id = int(old_slot_id_s)
    data = await state.get_data()
    if int(data.get("old_slot_id", -1)) != old_slot_id:
        await callback.answer("Сессия переноса недействительна.", show_alert=True)
        return
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
            day_callback_prefix=f"u_reschedule_day:{old_slot_id}:",
            month_callback_prefix=f"u_reschedule_month:{old_slot_id}:",
            back_callback="menu_bookings",
        )
    )


@consultation_router.callback_query(F.data.startswith("u_reschedule_day:"), StateFilter(RescheduleStates.choosing_date))
async def user_reschedule_day(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    _, rest = callback.data.split("u_reschedule_day:", 1)
    old_slot_id_s, day_iso = rest.split(":", 1)
    old_slot_id = int(old_slot_id_s)
    data = await state.get_data()
    if int(data.get("old_slot_id", -1)) != old_slot_id:
        await callback.answer("Сессия переноса недействительна.", show_alert=True)
        return

    day = datetime.strptime(day_iso, "%Y-%m-%d").date()
    start = datetime(day.year, day.month, day.day)
    end = start + timedelta(days=1)
    slots = get_available_slots(start, end)
    items = [(s.id, s.datetime.strftime("%H:%M")) for s in slots]

    await state.set_state(RescheduleStates.choosing_time)
    await state.update_data(old_slot_id=old_slot_id, day_iso=day_iso)
    await callback.message.edit_text(
        f"🔄 Перенос записи\n\nДата: {day.strftime('%d.%m.%Y')}\nВыберите время:",
        reply_markup=booking_times_kb(day_iso=day_iso, slot_items=[(sid, t) for sid, t in items]),
    )


@consultation_router.callback_query(F.data.startswith("u_book_time:"), StateFilter(RescheduleStates.choosing_time))
async def user_reschedule_pick_time(callback: CallbackQuery, state: FSMContext):
    """
    Reuse time picker callback for reschedule state.
    u_book_time:<slot_id>:<day_iso>
    """
    await callback.answer()
    _, slot_id_s, day_iso = callback.data.split(":", 2)
    new_slot_id = int(slot_id_s)
    data = await state.get_data()
    raw_old = data.get("old_slot_id")
    if raw_old is None:
        await callback.answer("Сессия переноса устарела. Откройте «Мои записи» снова.", show_alert=True)
        await state.clear()
        return
    old_slot_id = int(raw_old)
    user = get_user_by_chat_id(callback.from_user.id)

    old_slot = get_slot_by_id(old_slot_id)
    new_slot = get_slot_by_id(new_slot_id)
    if not user or not old_slot or not _user_owns_slot(old_slot, user):
        await callback.answer("Недостаточно прав.", show_alert=True)
        await state.clear()
        return
    if not new_slot or new_slot.status != "available" or not new_slot.is_available:
        await callback.message.edit_text("❌ Этот слот уже занят. Выберите другое время.")
        return

    await state.set_state(RescheduleStates.confirming)
    await state.update_data(new_slot_id=new_slot_id)
    await callback.message.edit_text(
        f"Перенести запись?\n\n"
        f"Было: {old_slot.datetime.strftime('%d.%m.%Y %H:%M')}\n"
        f"Стало: {new_slot.datetime.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Перенести", callback_data=f"u_reschedule_yes:{old_slot_id}:{new_slot_id}"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="menu_bookings"),
                ]
            ]
        ),
    )


@consultation_router.callback_query(F.data.startswith("u_reschedule_yes:"), StateFilter(RescheduleStates.confirming))
async def user_reschedule_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    _, old_s, new_s = callback.data.split(":", 2)
    old_slot_id = int(old_s)
    new_slot_id = int(new_s)

    data = await state.get_data()
    if int(data.get("old_slot_id", -1)) != old_slot_id or int(data.get("new_slot_id", -1)) != new_slot_id:
        await callback.answer("Данные переноса устарели. Откройте «Мои записи» и начните перенос снова.", show_alert=True)
        await state.clear()
        return

    old_slot = get_slot_by_id(old_slot_id)
    if not old_slot or not old_slot.client or callback.from_user.id != old_slot.client.chat_id:
        await callback.answer("Недостаточно прав.", show_alert=True)
        await state.clear()
        return

    ok = atomic_reschedule(business_id=1, old_slot_id=old_slot_id, new_slot_id=new_slot_id, created_by=callback.from_user.id)
    await state.clear()
    if not ok:
        await callback.message.edit_text("❌ Не удалось перенести: новый слот уже занят. Выберите другое время.")
        return
    await send_auto_delete_message(callback.bot, callback.from_user.id, "✅ Запись перенесена.", delay=2)
    await show_my_bookings(callback.message, edit=True)