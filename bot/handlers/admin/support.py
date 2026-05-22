from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from bot.filters.is_admin import IsAdmin
from bot.keyboards.inline.support import (
    admin_support_threads_kb,
    admin_support_thread_kb,
    admin_support_reply_kb,
    admin_support_message_actions_kb,
)
from bot.repositories.support import SupportRepository
from bot.states.support import AdminSupportStates
from bot.utils.ui import header, screen, italic
from bot.utils.messages import send_auto_delete_message


admin_support_router = Router()


async def _safe_edit(message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        raise


@admin_support_router.callback_query(F.data == "admin_support", IsAdmin())
async def support_threads(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    repo = SupportRepository()
    threads = repo.list_threads(limit=20)

    lines: list[str] = []
    if not threads:
        lines.append("Сообщений пока нет.")
    else:
        for t in threads:
            u = f"@{t.client_username}" if t.client_username else f"ID {t.client_id}"
            badge = f" 📨{t.unread_count}" if t.unread_count else ""
            lines.append(f"👤 {italic(u)}{badge} — {t.last_at}")
            if t.unread_count:
                last_unread = repo.get_last_unread_client_message(
                    business_id=SupportRepository.DEFAULT_BUSINESS_ID,
                    client_id=t.client_id,
                )
                preview = (last_unread.message[:60] + "…") if (last_unread and len(last_unread.message) > 60) else (last_unread.message if last_unread else "")
                lines.append(f"📝 {preview}" if preview else "📝 (нет данных)")
            else:
                lines.append("📝 Нет новых сообщений")
            lines.append("")
        if lines[-1] == "":
            lines.pop()

    kb_items = []
    for t in threads:
        u = f"@{t.client_username}" if t.client_username else f"ID {t.client_id}"
        badge = f" 📨{t.unread_count}" if t.unread_count else ""
        kb_items.append((t.client_id, f"👤 {u}{badge}"))

    await _safe_edit(
        callback.message,
        screen(header("💬", "Сообщения от клиентов"), lines),
        reply_markup=admin_support_threads_kb(kb_items),
    )


@admin_support_router.callback_query(F.data.startswith("admin_support_thread:"), IsAdmin())
async def support_thread(callback: CallbackQuery):
    await callback.answer()
    client_id = int(callback.data.split(":")[1])
    repo = SupportRepository()
    last_unread = repo.get_last_unread_client_message(business_id=SupportRepository.DEFAULT_BUSINESS_ID, client_id=client_id)
    # mark all unread client messages as read and reset counter
    repo.mark_client_messages_read(business_id=SupportRepository.DEFAULT_BUSINESS_ID, client_id=client_id)

    lines: list[str] = []
    actionable: list[int] = []
    if not last_unread:
        lines.append("Нет новых сообщений.")
    else:
        lines.append(f"👤 {last_unread.created_at.strftime('%d.%m %H:%M')}  ·  🆔{last_unread.id}")
        lines.append(last_unread.message)
        actionable = [last_unread.id]

    await _safe_edit(
        callback.message,
        screen(header("💬", f"Диалог: {client_id}"), lines or ["(пусто)"]),
        reply_markup=admin_support_message_actions_kb(client_id, actionable),
    )


@admin_support_router.callback_query(F.data.startswith("admin_support_delete_msg:"), IsAdmin())
async def support_delete_message(callback: CallbackQuery):
    await callback.answer()
    msg_id = int(callback.data.split(":")[1])
    repo = SupportRepository()
    m = repo.get(msg_id)
    if not m:
        await callback.answer("Сообщение не найдено.", show_alert=True)
        return
    ok = repo.soft_delete_message(message_id=msg_id, admin_id=callback.from_user.id)
    if not ok:
        await callback.answer("Не удалось удалить.", show_alert=True)
        return
    # Re-render thread
    await support_thread(callback)


@admin_support_router.callback_query(F.data.startswith("admin_support_reply:"), IsAdmin())
async def support_reply_from_forward(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    msg_id = int(callback.data.split(":")[1])
    repo = SupportRepository()
    m = repo.get(msg_id)
    if not m:
        await callback.message.edit_text("Сообщение не найдено.")
        return
    await state.clear()
    await state.update_data(client_id=int(m.client_id), client_username=m.client_username, reply_to_id=None)
    await state.set_state(AdminSupportStates.waiting_for_reply)
    await callback.message.edit_text(
        screen(header("↩️", "Ответ клиенту"), [f"Кому: {italic('@' + m.client_username) if m.client_username else italic(str(m.client_id))}", "Введите ответ:"]),
        reply_markup=admin_support_reply_kb(int(m.client_id)),
    )


@admin_support_router.callback_query(F.data.startswith("admin_support_reply_to:"), IsAdmin())
async def support_reply_from_thread(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    client_id = int(callback.data.split(":")[1])
    await state.clear()
    await state.update_data(client_id=client_id, client_username=None, reply_to_id=None)
    await state.set_state(AdminSupportStates.waiting_for_reply)
    await callback.message.edit_text(
        screen(header("↩️", "Ответ клиенту"), [f"Кому: {italic(str(client_id))}", "Введите ответ:"]),
        reply_markup=admin_support_reply_kb(client_id),
    )


@admin_support_router.message(AdminSupportStates.waiting_for_reply, IsAdmin())
async def support_send_reply(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите текст ответа.")
        return

    data = await state.get_data()
    client_id = int(data["client_id"])
    client_username = data.get("client_username")
    reply_to_id = data.get("reply_to_id")

    repo = SupportRepository()
    created = repo.create_admin_reply(
        business_id=SupportRepository.DEFAULT_BUSINESS_ID,
        client_id=client_id,
        client_username=client_username,
        admin_id=message.from_user.id,
        message=text,
        reply_to_id=int(reply_to_id) if reply_to_id else None,
    )

    # Auto-delete admin's typed message to keep chat clean
    try:
        import asyncio

        async def _delete_admin_msg():
            await asyncio.sleep(0.5)
            try:
                await message.delete()
            except Exception:
                pass

        asyncio.create_task(_delete_admin_msg())
    except Exception:
        pass

    # Send to user as inline notification (no plain chat reply)
    try:
        from bot.keyboards.inline.support import user_admin_message_kb

        await message.bot.send_message(
            client_id,
            f"💬 Сообщение от администратора\n\n{text}",
            reply_markup=user_admin_message_kb(admin_message_id=int(created.id)),
        )
    except Exception:
        pass

    await state.clear()
    await send_auto_delete_message(message.bot, message.from_user.id, "✅ Ответ отправлен.", delay=1)

