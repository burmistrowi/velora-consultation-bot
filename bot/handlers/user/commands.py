from aiogram import Router
from aiogram.types import Message
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from bot.database.methods.create import create_user
from bot.keyboards.inline.menu import get_main_menu_keyboard
from bot.misc.env import settings
from bot.repositories.support import SupportRepository

commands_router = Router()

@commands_router.message(Command('start'))
async def start_command(message: Message, state: FSMContext):
    # Админам показываем админ-панель отдельным хендлером
    if message.from_user.id in settings.admin_ids:
        return
    await state.clear()

    user = create_user(message.from_user.id, message.from_user.username)
    
    if user is None:
        text = "С возвращением в бот записи на консультации! 👋\n\n"
    else:
        text = "👋 Добро пожаловать в бот записи на консультации!\n\n"
    
    text += "Выберите действие:"

    unread = SupportRepository().unread_for_client(business_id=SupportRepository.DEFAULT_BUSINESS_ID, client_id=message.from_user.id)
    await message.answer(text, reply_markup=get_main_menu_keyboard(unread_support_count=unread))