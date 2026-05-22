from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from bot.keyboards.inline.menu import get_main_menu_keyboard
from bot.keyboards.inline.admin import get_admin_menu_keyboard
from bot.services.admin_access import get_admin_chat_ids_cached
from bot.handlers.user.consultation import show_schedule, show_my_bookings
from bot.database.methods.read import get_user_by_chat_id
from bot.misc.env import settings
from bot.repositories.support import SupportRepository
from bot.repositories.discounts import DiscountRepository

menu_router = Router()

@menu_router.callback_query(F.data == "menu_schedule")
async def menu_schedule(callback: CallbackQuery):
    await callback.answer()
    await show_schedule(callback.message, edit=True)

@menu_router.callback_query(F.data == "menu_bookings")
async def menu_bookings(callback: CallbackQuery):
    await callback.answer()
    await show_my_bookings(callback.message, edit=True)

@menu_router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user.id in get_admin_chat_ids_cached():
        unread = SupportRepository().unread_total()
        await callback.message.edit_text(
            "Выберите действие:",
            reply_markup=get_admin_menu_keyboard(unread_support_count=unread),
        )
        return
    unread_user = SupportRepository().unread_for_client(business_id=SupportRepository.DEFAULT_BUSINESS_ID, client_id=callback.from_user.id)
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=get_main_menu_keyboard(unread_support_count=unread_user)
    )


@menu_router.callback_query(F.data == "menu_profile")
async def menu_profile(callback: CallbackQuery):
    await callback.answer()
    user = get_user_by_chat_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Профиль не найден. Нажмите /start.", reply_markup=get_main_menu_keyboard())
        return

    uname = f"@{user.username}" if user.username else "—"

    discount_text = "—"
    if user.username:
        d = DiscountRepository().get_active_for_username(user.username)
        if d:
            if d.amount_type == "percent":
                discount_text = f"{d.amount_value}%"
            elif d.amount_type == "fixed":
                discount_text = f"{d.amount_value} {settings.CURRENCY_SYMBOL}"
            else:
                discount_text = str(d.amount_value)
    await callback.message.edit_text(
        f"👤 Профиль\n\n"
        f"Логин: {uname}\n"
        f"Номер чата: {user.chat_id}\n"
        f"Персональная скидка: {discount_text}\n",
        reply_markup=get_main_menu_keyboard(unread_support_count=SupportRepository().unread_for_client(business_id=SupportRepository.DEFAULT_BUSINESS_ID, client_id=callback.from_user.id)),
    )