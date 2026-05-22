from __future__ import annotations

from bot.misc.env import settings
from bot.repositories.admins import AdminRepository
from bot.services.cache import TTLCache


_admins_cache: TTLCache[set[int]] = TTLCache(ttl_seconds=60)


def get_admin_chat_ids_cached() -> set[int]:
    def factory() -> set[int]:
        repo = AdminRepository()
        ids = {a.chat_id for a in repo.list()}
        ids.update(settings.admin_ids)
        return ids

    return _admins_cache.get_or_set("admin_chat_ids", factory)


def invalidate_admin_cache() -> None:
    _admins_cache.invalidate("admin_chat_ids")

