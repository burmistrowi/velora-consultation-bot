from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from datetime import datetime
from bot.filters.is_admin import IsAdmin
from bot.database.methods.create import create_slot
from bot.database.methods.read import get_all_slots
from bot.misc.env import settings
from bot.keyboards.inline.admin import (
    get_admin_menu_keyboard,
    get_back_to_admin_menu_keyboard,
    get_cancel_admin_add_slot_keyboard,
)
from bot.repositories.support import SupportRepository
from bot.states.admin import AdminSlotStates
from bot.utils.ru_labels import time_slot_status_ru

admin_consultation_router = Router()

@admin_consultation_router.callback_query(F.data == "admin_back_to_menu", IsAdmin())
async def admin_back_to_menu(callback: CallbackQuery):
    await callback.answer()
    unread = SupportRepository().unread_total()
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=get_admin_menu_keyboard(unread_support_count=unread),
    )


@admin_consultation_router.callback_query(F.data == "admin_add_slot", IsAdmin())
async def admin_add_slot(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminSlotStates.waiting_for_slot)
    await callback.message.edit_text(
        "Введите новый слот в формате:\n"
        "YYYY-MM-DD HH:MM\n"
        "Например: 2026-05-20 15:00",
        reply_markup=get_cancel_admin_add_slot_keyboard(),
    )


@admin_consultation_router.callback_query(F.data == "admin_cancel_add_slot", IsAdmin())
async def admin_cancel_add_slot(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    unread = SupportRepository().unread_total()
    await callback.message.edit_text(
        "Отменено. Выберите действие:",
        reply_markup=get_admin_menu_keyboard(unread_support_count=unread),
    )


@admin_consultation_router.message(AdminSlotStates.waiting_for_slot, IsAdmin())
async def add_new_slot(message: Message, state: FSMContext):
    try:
        date_str, time_str = message.text.split()
        slot_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        
        new_slot = create_slot(slot_datetime)
        await message.answer(
            f"✅ Добавлен новый слот:\n"
            f"📅 Дата: {slot_datetime.strftime('%d.%m.%Y %H:%M')}\n"
        )
        await state.clear()
        unread = SupportRepository().unread_total()
        await message.answer("Выберите действие:", reply_markup=get_admin_menu_keyboard(unread_support_count=unread))
    except Exception as e:
        await message.answer(
            "❌ Ошибка при добавлении слота.\n"
            "Используйте формат: YYYY-MM-DD HH:MM\n"
            "Например: 2026-05-20 15:00"
        )

@admin_consultation_router.callback_query(F.data == "admin_view_slots", IsAdmin())
async def view_slots(callback: CallbackQuery):
    from_date = datetime.now()
    slots = get_all_slots(from_date)
    
    if not slots:
        await callback.answer()
        await callback.message.edit_text(
            "Нет доступных слотов.",
            reply_markup=get_back_to_admin_menu_keyboard(),
        )
        return
    
    _st_emoji = {
        "available": "🔓",
        "pending_confirmation": "⏳",
        "active": "✅",
        "cancelled": "❌",
        "rescheduled": "🔁",
        "completed": "✨",
    }
    response = "📅 Список всех слотов:\n\n"
    for slot in slots:
        em = _st_emoji.get(slot.status, "❓")
        status = f"{em} {time_slot_status_ru(slot.status)}"
        slot_info = f"{slot.datetime.strftime('%d.%m.%Y %H:%M')} - {status}"
        
        if slot.status in ('pending_confirmation', 'active') and slot.client:
            slot_info += f"\nЗабронировал: @{slot.client.username or 'Без username'}"
        
        response += f"{slot_info}\n\n"
    
    await callback.answer()
    await callback.message.edit_text(response, reply_markup=get_back_to_admin_menu_keyboard())