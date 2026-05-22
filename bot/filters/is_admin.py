from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union
from bot.services.admin_access import get_admin_chat_ids_cached

class IsAdmin(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        if not getattr(event, "from_user", None):
            return False
        return event.from_user.id in get_admin_chat_ids_cached()
