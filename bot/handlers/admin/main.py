from aiogram import Router
from typing import Tuple

from .commands import commands_router
from .panel import panel_router
from .services import admin_services_router
from .slots import admin_slots_router
from .bookings import admin_bookings_router
from .admins import admin_admins_router
from .discounts import admin_discounts_router
from .support import admin_support_router
from .schedule import admin_schedule_router

def register_handlers(up_router: Router) -> Tuple[Router, ...]:
    return (
        commands_router,
        panel_router,
        admin_services_router,
        admin_slots_router,
        admin_schedule_router,
        admin_bookings_router,
        admin_support_router,
        admin_admins_router,
        admin_discounts_router,
    )