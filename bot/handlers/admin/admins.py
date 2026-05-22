from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.database.methods.read import get_user_by_username
from bot.filters.is_admin import IsAdmin
from bot.keyboards.inline.admin_admins import admins_list_kb, admin_actions_kb, confirm_add_admin_kb
from bot.repositories.admins import AdminRepository
from bot.services.admin_access import invalidate_admin_cache
from bot.states.admin import AdminAdminsStates
from bot.utils.ui import header, screen, italic


admin_admins_router = Router()


def _admins_text(admins) -> str:
    lines: list[str] = []
    if not admins:
        lines.append("Список пуст.")
    else:
        for a in admins:
            uname = f"@{a.username}" if a.username else "—"
            lines.extend([f"👤 {italic(uname)}", f"Роль: {italic(a.role)}", ""])
        if lines[-1] == "":
            lines.pop()
    return screen(header("👥", "Администраторы"), lines)


@admin_admins_router.callback_query(F.data == "admin_admins", IsAdmin())
async def admins_list(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    repo = AdminRepository()
    admins = repo.list()
    await callback.message.edit_text(_admins_text(admins), reply_markup=admins_list_kb([a.id for a in admins]))


@admin_admins_router.callback_query(F.data.startswith("admin_admin:"), IsAdmin())
async def admin_details(callback: CallbackQuery):
    await callback.answer()
    admin_id = int(callback.data.split(":")[1])
    repo = AdminRepository()
    admins = repo.list()
    a = next((x for x in admins if x.id == admin_id), None)
    if not a:
        await callback.message.edit_text(screen(header("👥", "Администраторы"), ["Администратор не найден."]))
        return
    uname = f"@{a.username}" if a.username else "—"
    text = screen(header("👥", "Администратор"), [f"👤 {italic(uname)}", f"Роль: {italic(a.role)}"])
    await callback.message.edit_text(text, reply_markup=admin_actions_kb(admin_id))


@admin_admins_router.callback_query(F.data == "admin_admin_add", IsAdmin())
async def admin_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(AdminAdminsStates.waiting_for_username)
    await callback.message.edit_text(
        screen(header("➕", "Добавить администратора"), ["Введите username (например: @username):"])
    )


@admin_admins_router.message(AdminAdminsStates.waiting_for_username, IsAdmin())
async def admin_add_username(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    username = raw.lstrip("@")
    if not username:
        await message.answer("Введите корректный username.")
        return

    user = get_user_by_username(username)
    if not user:
        await message.answer(
            screen(header("❌", "Не найдено"), ["Пользователь не найден в базе. Он должен хотя бы раз нажать /start."])
        )
        return

    await state.update_data(username=username, chat_id=user.chat_id)
    await state.set_state(AdminAdminsStates.waiting_for_confirm)
    await message.answer(
        screen(header("✅", "Подтверждение"), [f"Добавить @{username} в администраторы?"]),
        reply_markup=confirm_add_admin_kb(username),
    )


@admin_admins_router.callback_query(F.data.startswith("admin_admin_confirm_add:"), IsAdmin())
async def admin_add_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    username = data.get("username")
    chat_id = data.get("chat_id")
    if not username or not chat_id:
        await state.clear()
        await callback.message.edit_text(screen(header("❌", "Ошибка"), ["Сессия устарела. Попробуйте снова."]))
        return

    repo = AdminRepository()
    repo.add(chat_id=int(chat_id), username=username, role="admin")
    invalidate_admin_cache()
    await state.clear()
    admins = repo.list()
    await callback.message.edit_text(
        screen(header("👥", "Администраторы"), ["✅ Добавлено."]),
        reply_markup=admins_list_kb([a.id for a in admins]),
    )


@admin_admins_router.callback_query(F.data.startswith("admin_admin_delete:"), IsAdmin())
async def admin_delete(callback: CallbackQuery):
    await callback.answer()
    admin_id = int(callback.data.split(":")[1])
    repo = AdminRepository()
    ok = repo.delete(admin_id)
    invalidate_admin_cache()
    admins = repo.list()
    await callback.message.edit_text(
        screen(header("👥", "Администраторы"), ["✅ Удалено." if ok else "Не найдено."]),
        reply_markup=admins_list_kb([a.id for a in admins]),
    )

