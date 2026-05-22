from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.filters.is_admin import IsAdmin
from bot.keyboards.inline.admin import get_admin_menu_keyboard
from bot.repositories.support import SupportRepository
from bot.utils.ui import header, screen


panel_router = Router()


def admin_menu_text() -> str:
    return screen(
        header("🛠", "Админ-панель"),
        ["Выберите раздел:"],
    )


@panel_router.callback_query(F.data == "admin_back_to_menu", IsAdmin())
async def admin_back_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    unread = SupportRepository().unread_total()
    await callback.message.edit_text(admin_menu_text(), reply_markup=get_admin_menu_keyboard(unread_support_count=unread))


@panel_router.message(F.text == "/admin", IsAdmin())
async def open_admin_menu(message: Message, state: FSMContext):
    await state.clear()
    unread = SupportRepository().unread_total()
    await message.answer(admin_menu_text(), reply_markup=get_admin_menu_keyboard(unread_support_count=unread))

