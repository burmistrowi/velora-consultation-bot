from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter

from bot.filters.is_admin import IsAdmin
from bot.keyboards.inline.menu import get_main_menu_keyboard
from bot.keyboards.inline.admin import get_admin_menu_keyboard
from bot.services.admin_access import get_admin_chat_ids_cached
from bot.repositories.support import SupportRepository


other_router = Router()

@other_router.callback_query(F.data == "notif_ok")
async def notif_ok(callback):
    await callback.answer("Ок")
    # Optional: remove buttons after acknowledgement
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

@other_router.callback_query(F.data == "ignore")
async def ignore_callback(callback):
    await callback.answer()

@other_router.message(StateFilter(None), IsAdmin())
async def admin_please_use_buttons(msg: Message):
    unread = SupportRepository().unread_total()
    await msg.answer(
        "Пожалуйста, используйте inline-кнопки.",
        reply_markup=get_admin_menu_keyboard(unread_support_count=unread),
    )


@other_router.message(StateFilter(None))
async def user_please_use_buttons(msg: Message):
    if msg.from_user.id in get_admin_chat_ids_cached():
        return
    unread = SupportRepository().unread_for_client(business_id=SupportRepository.DEFAULT_BUSINESS_ID, client_id=msg.from_user.id)
    await msg.answer(
        "Пожалуйста, используйте inline-кнопки.",
        reply_markup=get_main_menu_keyboard(unread_support_count=unread),
    )
