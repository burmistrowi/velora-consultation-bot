from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.filters.is_admin import IsAdmin
from bot.keyboards.inline.admin_services import (
    services_list_kb,
    service_actions_kb,
    confirm_save_service_kb,
)
from bot.repositories.services import ServiceRepository
from bot.states.admin import AdminServiceStates
from bot.utils.ui import plain_header, screen, format_price_integer_ru
from bot.config import SERVICE_EMOJI


admin_services_router = Router()


def _services_text(services) -> str:
    lines: list[str] = []
    if not services:
        lines.append("Список пуст.")
    else:
        for s in services:
            lines.extend(
                [
                    f"{SERVICE_EMOJI} {s.name}",
                    f"💰 {format_price_integer_ru(s.price)}",
                    f"⏱ {s.duration_min} мин",
                    "",
                ]
            )
        if lines and lines[-1] == "":
            lines.pop()
    return screen(plain_header("✂️", "Услуги"), lines)


@admin_services_router.callback_query(F.data == "admin_services", IsAdmin())
async def services_list(callback: CallbackQuery):
    repo = ServiceRepository()
    services = repo.list(active_only=False)
    await callback.answer()
    await callback.message.edit_text(
        _services_text(services),
        reply_markup=services_list_kb([(s.id, s.name) for s in services]),
    )


@admin_services_router.callback_query(F.data.startswith("admin_service:"), IsAdmin())
async def service_details(callback: CallbackQuery):
    service_id = int(callback.data.split(":")[1])
    repo = ServiceRepository()
    s = repo.get(service_id)
    await callback.answer()
    if not s:
        await callback.message.edit_text(
            screen(plain_header("✂️", "Услуги"), ["Услуга не найдена."]),
            reply_markup=services_list_kb([(x.id, x.name) for x in repo.list(active_only=False)]),
        )
        return
    text = screen(
        plain_header("✂️", "Услуга"),
        [
            f"Название: {SERVICE_EMOJI} {s.name}",
            f"Цена: {format_price_integer_ru(s.price)}",
            f"Длительность: {s.duration_min} мин",
        ],
    )
    await callback.message.edit_text(text, reply_markup=service_actions_kb(service_id))


@admin_services_router.callback_query(F.data == "admin_service_add", IsAdmin())
async def service_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(AdminServiceStates.waiting_for_name)
    await callback.message.edit_text(
        screen(plain_header("➕", "Новая услуга"), ["Введите название услуги:"]),
        reply_markup=None,
    )


@admin_services_router.callback_query(F.data.startswith("admin_service_edit:"), IsAdmin())
async def service_edit_start(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":")[1])
    repo = ServiceRepository()
    s = repo.get(service_id)
    await callback.answer()
    if not s:
        await callback.message.edit_text(screen(plain_header("✂️", "Услуги"), ["Услуга не найдена."]))
        return
    await state.clear()
    await state.update_data(service_id=service_id, action="edit")
    await state.set_state(AdminServiceStates.waiting_for_name)
    await callback.message.edit_text(
        screen(plain_header("✏️", "Редактирование услуги"), [f"Текущее: {s.name}", "Введите новое название:"]),
    )


@admin_services_router.callback_query(F.data.startswith("admin_service_delete:"), IsAdmin())
async def service_delete(callback: CallbackQuery):
    service_id = int(callback.data.split(":")[1])
    repo = ServiceRepository()
    await callback.answer()
    ok = repo.delete(service_id)
    services = repo.list(active_only=False)
    await callback.message.edit_text(
        screen(plain_header("✂️", "Услуги"), ["✅ Удалено." if ok else "Не найдено."]),
        reply_markup=services_list_kb([(s.id, s.name) for s in services]),
    )


@admin_services_router.message(AdminServiceStates.waiting_for_name, IsAdmin())
async def service_name_step(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Введите непустое название.")
        return
    await state.update_data(name=name)
    await state.set_state(AdminServiceStates.waiting_for_price)
    await message.answer(screen(plain_header("💰", "Цена"), ["Введите цену целым числом (например: 1500):"]))


@admin_services_router.message(AdminServiceStates.waiting_for_price, IsAdmin())
async def service_price_step(message: Message, state: FSMContext):
    raw = (message.text or "").replace(",", ".").strip()
    try:
        price = int(round(float(raw)))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректную цену целым числом (например: 1500).")
        return
    await state.update_data(price=float(price))
    await state.set_state(AdminServiceStates.waiting_for_duration)
    await message.answer(screen(plain_header("⏱", "Длительность"), ["Введите длительность в минутах (целое число):"]))


@admin_services_router.message(AdminServiceStates.waiting_for_duration, IsAdmin())
async def service_duration_step(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    try:
        duration = int(raw)
        if duration <= 0 or duration > 24 * 60:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректную длительность в минутах (например: 60).")
        return

    data = await state.get_data()
    action = data.get("action", "create")
    await state.update_data(duration_min=duration)
    await state.set_state(AdminServiceStates.waiting_for_confirm)

    name = data["name"]
    price = data["price"]
    service_id = data.get("service_id")
    text = screen(
        plain_header("✅", "Подтверждение"),
        [
            f"Название: {name}",
            f"Цена: {format_price_integer_ru(price)}",
            f"Длительность: {duration} мин",
            "",
            "Сохранить изменения?",
        ],
    )
    await message.answer(text, reply_markup=confirm_save_service_kb(action, service_id))


@admin_services_router.callback_query(F.data.startswith("admin_service_confirm:"), IsAdmin())
async def service_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    payload = callback.data.split(":", 1)[1]  # action[:id]
    action, *rest = payload.split(":")
    data = await state.get_data()
    repo = ServiceRepository()

    if action == "edit":
        service_id = int(rest[0]) if rest else int(data.get("service_id"))
        ok = repo.update(
            service_id,
            name=data["name"],
            price=data["price"],
            duration_min=data["duration_min"],
        )
        msg = "✅ Сохранено." if ok else "❌ Услуга не найдена."
    else:
        repo.create(name=data["name"], price=data["price"], duration_min=data["duration_min"])
        msg = "✅ Добавлено."

    await state.clear()
    services = repo.list(active_only=False)
    await callback.message.edit_text(
        screen(plain_header("✂️", "Услуги"), [msg]),
        reply_markup=services_list_kb([(s.id, s.name) for s in services]),
    )

