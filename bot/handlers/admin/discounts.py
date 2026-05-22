from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.filters.is_admin import IsAdmin
from bot.keyboards.inline.admin_discounts import (
    discounts_list_kb,
    discount_actions_kb,
    discount_type_kb,
    confirm_discount_kb,
    discount_amount_nav_kb,
)
from bot.keyboards.inline.admin_discount_services import discount_services_pick_kb
from bot.misc.env import settings
from bot.repositories.discounts import DiscountRepository
from bot.repositories.services import ServiceRepository
from bot.states.admin import AdminDiscountStates
from bot.utils.ui import header, screen, italic, bold_italic


admin_discounts_router = Router()


def _discounts_text(discounts) -> str:
    lines: list[str] = []
    if not discounts:
        lines.append("Список пуст.")
    else:
        for d in discounts:
            value = f"{d.amount_value}%" if d.amount_type == "percent" else f"{d.amount_value} {settings.CURRENCY_SYMBOL}"
            applies = "все услуги" if d.applies_to == "all" else "выбранные"
            lines.extend(
                [
                    f"💸 Скидка: {bold_italic(value)}",
                    f"Применяется к: {italic(applies)}",
                    f"Пользователь: {italic('@' + d.username)}",
                    "",
                ]
            )
        if lines[-1] == "":
            lines.pop()
    return screen(header("💸", "Скидки"), lines)


@admin_discounts_router.callback_query(F.data == "admin_discounts", IsAdmin())
async def discounts_list(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    repo = DiscountRepository()
    discounts = repo.list(active_only=False)
    await callback.message.edit_text(_discounts_text(discounts), reply_markup=discounts_list_kb([d.id for d in discounts]))


@admin_discounts_router.callback_query(F.data.startswith("admin_discount:"), IsAdmin())
async def discount_details(callback: CallbackQuery):
    await callback.answer()
    discount_id = int(callback.data.split(":")[1])
    repo = DiscountRepository()
    d = repo.get(discount_id)
    if not d:
        await callback.message.edit_text(screen(header("💸", "Скидки"), ["Скидка не найдена."]))
        return
    value = f"{d.amount_value}%" if d.amount_type == "percent" else f"{d.amount_value} {settings.CURRENCY_SYMBOL}"
    applies = "все услуги" if d.applies_to == "all" else "выбранные"
    text = screen(
        header("💸", "Скидка"),
        [
            f"💸 Скидка: {bold_italic(value)}",
            f"Применяется к: {italic(applies)}",
            f"Пользователь: {italic('@' + d.username)}",
        ],
    )
    await callback.message.edit_text(text, reply_markup=discount_actions_kb(discount_id))


@admin_discounts_router.callback_query(F.data == "admin_discount_add", IsAdmin())
async def discount_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(AdminDiscountStates.waiting_for_type)
    await callback.message.edit_text(
        screen(header("➕", "Новая скидка"), ["Выберите тип скидки:"]),
        reply_markup=discount_type_kb(),
    )


@admin_discounts_router.callback_query(F.data.startswith("admin_discount_type:"), IsAdmin())
async def discount_type_step(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    applies_to = callback.data.split(":")[1]
    await state.update_data(applies_to=applies_to)
    if applies_to == "selected":
        await state.update_data(service_ids=[])
        await callback.message.edit_text(
            screen(header("✂️", "Выбор услуг"), ["Выберите услуги, к которым применяется скидка:"]),
            reply_markup=discount_services_pick_kb(
                [(s.id, s.name) for s in ServiceRepository().list(active_only=True)],
                selected=set(),
            ),
        )
        return

    await state.set_state(AdminDiscountStates.waiting_for_amount)
    await callback.message.edit_text(
        screen(
            header("💸", "Размер скидки"),
            [
                "Введите скидку в формате:",
                italic("20%  или  500"),
                "Если без %, будет считаться фиксированной суммой в валюте.",
            ],
        )
        ,
        reply_markup=discount_amount_nav_kb(),
    )


@admin_discounts_router.callback_query(F.data.startswith("admin_discount_srv_toggle:"), IsAdmin())
async def discount_toggle_service(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    sid = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("service_ids") or [])
    if sid in selected:
        selected.remove(sid)
    else:
        selected.add(sid)
    await state.update_data(service_ids=sorted(selected))
    await callback.message.edit_reply_markup(
        reply_markup=discount_services_pick_kb(
            [(s.id, s.name) for s in ServiceRepository().list(active_only=True)],
            selected=selected,
        )
    )


@admin_discounts_router.callback_query(F.data == "admin_discount_srv_done", IsAdmin())
async def discount_services_done(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    selected = set(data.get("service_ids") or [])
    if not selected:
        await callback.answer("Выберите хотя бы одну услугу", show_alert=True)
        return
    await state.update_data(service_ids=sorted(selected))
    await state.set_state(AdminDiscountStates.waiting_for_amount)
    await callback.message.edit_text(
        screen(
            header("💸", "Размер скидки"),
            [
                "Введите скидку в формате:",
                italic("20%  или  500"),
                "Если без %, будет считаться фиксированной суммой в валюте.",
            ],
        )
        ,
        reply_markup=discount_amount_nav_kb(),
    )


@admin_discounts_router.callback_query(F.data == "admin_discount_amount_menu", IsAdmin())
async def discount_amount_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    from bot.keyboards.inline.admin import get_admin_menu_keyboard
    from bot.repositories.support import SupportRepository

    unread = SupportRepository().unread_total()
    await callback.message.edit_text("Выберите действие:", reply_markup=get_admin_menu_keyboard(unread_support_count=unread))


@admin_discounts_router.callback_query(F.data == "admin_discount_amount_back", IsAdmin())
async def discount_amount_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    applies_to = data.get("applies_to")

    await state.set_state(AdminDiscountStates.waiting_for_type)
    if applies_to == "selected":
        await callback.message.edit_text(
            screen(header("✂️", "Выбор услуг"), ["Выберите услуги, к которым применяется скидка:"]),
            reply_markup=discount_services_pick_kb(
                [(s.id, s.name) for s in ServiceRepository().list(active_only=True)],
                selected=set(data.get("service_ids") or []),
            ),
        )
        return

    await callback.message.edit_text(
        screen(header("➕", "Новая скидка"), ["Выберите тип скидки:"]),
        reply_markup=discount_type_kb(),
    )


@admin_discounts_router.message(AdminDiscountStates.waiting_for_amount, IsAdmin())
async def discount_amount_step(message: Message, state: FSMContext):
    raw = (message.text or "").strip().replace(",", ".")
    amount_type = "fixed"
    if raw.endswith("%"):
        amount_type = "percent"
        raw = raw[:-1].strip()
    try:
        value = float(raw)
        if value <= 0:
            raise ValueError
        if amount_type == "percent" and value > 100:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректное значение (например: 20% или 500).")
        return

    await state.update_data(amount_type=amount_type, amount_value=value)
    await state.set_state(AdminDiscountStates.waiting_for_username)
    await message.answer(screen(header("👤", "Пользователь"), ["Введите username (например: @username):"]))


@admin_discounts_router.message(AdminDiscountStates.waiting_for_username, IsAdmin())
async def discount_username_step(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    username = raw.lstrip("@")
    if not username:
        await message.answer("Введите корректный username.")
        return

    await state.update_data(username=username)
    await state.set_state(AdminDiscountStates.waiting_for_confirm)

    data = await state.get_data()
    value = f"{data['amount_value']}%" if data["amount_type"] == "percent" else f"{data['amount_value']} {settings.CURRENCY_SYMBOL}"
    applies = "все услуги" if data["applies_to"] == "all" else "выбранные"

    await message.answer(
        screen(
            header("✅", "Подтверждение"),
            [
                f"💸 Скидка: {bold_italic(value)}",
                f"Применяется к: {italic(applies)}",
                f"Пользователь: {italic('@' + username)}",
                "",
                "Сохранить?",
            ],
        ),
        reply_markup=confirm_discount_kb(),
    )


@admin_discounts_router.callback_query(F.data == "admin_discount_confirm", IsAdmin())
async def discount_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    repo = DiscountRepository()
    repo.create(
        username=data["username"],
        applies_to=data["applies_to"],
        amount_type=data["amount_type"],
        amount_value=data["amount_value"],
        service_ids=sorted(list(set(data.get("service_ids") or []))) or None,
    )
    await state.clear()
    discounts = repo.list(active_only=False)
    await callback.message.edit_text(
        screen(header("💸", "Скидки"), ["✅ Сохранено."]),
        reply_markup=discounts_list_kb([d.id for d in discounts]),
    )


@admin_discounts_router.callback_query(F.data.startswith("admin_discount_delete:"), IsAdmin())
async def discount_delete(callback: CallbackQuery):
    await callback.answer()
    discount_id = int(callback.data.split(":")[1])
    repo = DiscountRepository()
    ok = repo.delete(discount_id)
    discounts = repo.list(active_only=False)
    await callback.message.edit_text(
        screen(header("💸", "Скидки"), ["✅ Удалено." if ok else "Не найдено."]),
        reply_markup=discounts_list_kb([d.id for d in discounts]),
    )

