from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu_keyboard(*, unread_support_count: int = 0) -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню"""
    support_label = "💬 Сообщения от администратора"
    if unread_support_count:
        support_label = f"💬 Сообщения от администратора 📨{unread_support_count}"
    keyboard = [
        [
            InlineKeyboardButton(
                text="📅 Записаться",
                callback_data="menu_schedule"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Мои записи",
                callback_data="menu_bookings"
            )
        ],
        [
            InlineKeyboardButton(
                text=support_label,
                callback_data="menu_support_inbox"
            )
        ],
        [
            InlineKeyboardButton(
                text="👤 Профиль",
                callback_data="menu_profile"
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой возврата в меню"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="back_to_menu"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 