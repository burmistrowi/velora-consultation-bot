from aiogram import Router
from aiogram.types import Message
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from bot.filters.is_admin import IsAdmin
from bot.database.methods.create import create_user
from bot.keyboards.inline.admin import get_admin_menu_keyboard
from bot.repositories.support import SupportRepository
from bot.utils.ui import header, screen

commands_router = Router()

@commands_router.message(Command('start'), IsAdmin())
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    create_user(message.from_user.id, message.from_user.username)
    
    unread = SupportRepository().unread_total()
    await message.answer(
        screen(header("🛠", "Админ-панель"), ["Выберите раздел:"]),
        reply_markup=get_admin_menu_keyboard(unread_support_count=unread)
    )