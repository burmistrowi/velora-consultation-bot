from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.inline.common import keyboard


def user_support_start_kb() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu"),
            ]
        ]
    )


def user_support_cancel_kb() -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="support_cancel"),
                InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu"),
            ]
        ]
    )


def admin_support_threads_kb(threads: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for chat_id, label in threads:
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_support_thread:{chat_id}")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_support")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu")])
    return keyboard(rows)


def admin_support_thread_kb(user_chat_id: int) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [InlineKeyboardButton(text="✍️ Ответить", callback_data=f"admin_support_reply_to:{user_chat_id}")],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_support"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu"),
            ],
        ]
    )


def admin_support_reply_kb(user_chat_id: int) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_support_thread:{user_chat_id}"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu"),
            ]
        ]
    )


def admin_support_reply_button(message_id: int) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [InlineKeyboardButton(text="↩️ Ответить", callback_data=f"admin_support_reply:{message_id}")],
        ]
    )


def admin_support_message_actions_kb(client_id: int, message_ids: list[int]) -> InlineKeyboardMarkup:
    """
    Inline actions for messages inside a dialog:
    - Delete a specific message (soft-delete)
    """
    rows: list[list[InlineKeyboardButton]] = []
    for mid in message_ids:
        rows.append(
            [
                InlineKeyboardButton(text=f"🗑 Удалить #{mid}", callback_data=f"admin_support_delete_msg:{mid}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="✍️ Ответить", callback_data=f"admin_support_reply_to:{client_id}")])
    rows.append(
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_support"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="admin_back_to_menu"),
        ]
    )
    return keyboard(rows)


def user_support_inbox_kb(*, client_id: int, message_ids: list[int]) -> InlineKeyboardMarkup:
    """
    User inbox actions:
    - Delete own messages (soft-delete)
    - Write new message
    """
    rows: list[list[InlineKeyboardButton]] = []
    for mid in message_ids:
        rows.append([InlineKeyboardButton(text=f"🗑 Удалить #{mid}", callback_data=f"user_support_delete_msg:{mid}")])
    rows.append([InlineKeyboardButton(text="✍️ Написать сообщение", callback_data="menu_support")])
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")])
    return keyboard(rows)


def user_admin_message_kb(*, admin_message_id: int) -> InlineKeyboardMarkup:
    """
    Notification keyboard for a new admin->client message.
    """
    return keyboard(
        [
            [InlineKeyboardButton(text="↩️ Ответить", callback_data=f"user_support_reply_to:{admin_message_id}")],
            [InlineKeyboardButton(text="📥 Открыть диалог", callback_data="menu_support_inbox")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
        ]
    )

