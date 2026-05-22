from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_menu_keyboard(*, unread_support_count: int = 0) -> InlineKeyboardMarkup:
    support_label = "💬 Сообщения от клиентов"
    if unread_support_count:
        support_label = f"💬 Сообщения от клиентов 📨{unread_support_count}"
    keyboard = [
        [InlineKeyboardButton(text="✂️ Услуги", callback_data="admin_services")],
        [InlineKeyboardButton(text="📅 Слоты", callback_data="admin_slots")],
        [InlineKeyboardButton(text="📋 Записи", callback_data="admin_bookings")],
        [InlineKeyboardButton(text=support_label, callback_data="admin_support")],
        [InlineKeyboardButton(text="👥 Администраторы", callback_data="admin_admins")],
        [InlineKeyboardButton(text="💸 Скидки", callback_data="admin_discounts")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_to_admin_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu")]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_cancel_admin_add_slot_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel_add_slot")]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

