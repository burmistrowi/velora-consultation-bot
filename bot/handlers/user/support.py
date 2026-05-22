from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.keyboards.inline.support import user_support_cancel_kb
from bot.repositories.support import SupportRepository
from bot.services.admin_access import get_admin_chat_ids_cached
from bot.states.support import UserSupportStates
from bot.keyboards.inline.support import user_support_inbox_kb
from bot.keyboards.inline.support import user_admin_message_kb
from bot.utils.ui import header, screen
from bot.utils.messages import send_auto_delete_message
from bot.keyboards.inline.menu import get_main_menu_keyboard


user_support_router = Router()


@user_support_router.callback_query(F.data == "menu_support")
async def support_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(UserSupportStates.waiting_for_message)
    await callback.message.edit_text(
        "💬 Связаться с администратором\n\n"
        "Напишите сообщение — оно появится в админ-панели в разделе «Сообщения от клиентов».",
        reply_markup=user_support_cancel_kb(),
    )


@user_support_router.callback_query(F.data == "menu_support_inbox")
async def support_inbox(callback: CallbackQuery):
    await callback.answer()
    repo = SupportRepository()
    last_unread = repo.get_last_unread_admin_message(
        business_id=SupportRepository.DEFAULT_BUSINESS_ID,
        client_id=callback.from_user.id,
    )
    # mark all unread admin replies as read
    repo.mark_admin_messages_read(business_id=SupportRepository.DEFAULT_BUSINESS_ID, client_id=callback.from_user.id)

    lines: list[str] = []
    if not last_unread:
        lines.append("Нет новых сообщений.")
    else:
        lines.append(f"🛠 {last_unread.created_at.strftime('%d.%m %H:%M')}  ·  🆔{last_unread.id}")
        lines.append(last_unread.message)

    deletable: list[int] = []
    # allow deleting only own last client message if needed - keep existing behavior for last 5 in full history mode.
    await callback.message.edit_text(
        screen(header("💬", "Диалог с администратором"), lines or ["(пока пусто)"]),
        reply_markup=user_support_inbox_kb(client_id=callback.from_user.id, message_ids=deletable),
    )


@user_support_router.callback_query(F.data.startswith("user_support_reply_to:"))
async def user_support_reply_to(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    admin_msg_id = int(callback.data.split(":")[1])
    await state.clear()
    await state.update_data(reply_to_id=admin_msg_id)
    await state.set_state(UserSupportStates.waiting_for_message)
    await callback.message.edit_text(
        "✍️ Ответ администратору\n\nНапишите сообщение:",
        reply_markup=user_support_cancel_kb(),
    )


@user_support_router.callback_query(F.data.startswith("user_support_delete_msg:"))
async def user_support_delete_msg(callback: CallbackQuery):
    await callback.answer()
    msg_id = int(callback.data.split(":")[1])
    repo = SupportRepository()
    ok = repo.soft_delete_client_message(message_id=msg_id, client_id=callback.from_user.id)
    if not ok:
        await callback.answer("Не удалось удалить.", show_alert=True)
        return
    await support_inbox(callback)


@user_support_router.callback_query(F.data == "support_cancel")
async def support_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Отменено.", reply_markup=None)


@user_support_router.message(UserSupportStates.waiting_for_message)
async def support_message(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    # Auto-delete user's message after 1 second to keep chat clean
    try:
        import asyncio

        async def _delete_user_msg():
            await asyncio.sleep(1)
            try:
                await message.delete()
            except Exception:
                pass

        asyncio.create_task(_delete_user_msg())
    except Exception:
        pass

    repo = SupportRepository()
    data = await state.get_data()
    reply_to_id = data.get("reply_to_id")
    repo.create_client_message(
        business_id=SupportRepository.DEFAULT_BUSINESS_ID,
        client_id=message.from_user.id,
        client_username=message.from_user.username,
        message=text,
        reply_to_id=int(reply_to_id) if reply_to_id else None,
    )

    # IMPORTANT: no push-notifications to admins (badge only in admin menu)

    await state.clear()
    await send_auto_delete_message(
        message.bot,
        message.from_user.id,
        "✅ Сообщение отправлено.",
        delay=2,
    )
    # Redirect user back to main menu automatically
    unread = SupportRepository().unread_for_client(business_id=SupportRepository.DEFAULT_BUSINESS_ID, client_id=message.from_user.id)
    await message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(unread_support_count=unread))

