from aiogram import Router
from bot.handlers import user, admin
from bot.middlewares.delete_user_messages import DeleteUserMessageMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.handlers.other import other_router

async def register_all_handlers(up_router: Router, **kwargs) -> None:
    routers = (
        *admin.register_handlers(up_router),
        *user.register_handlers(up_router, bot=kwargs['bot']),
        other_router,
    )

    up_router.message.middleware(ThrottlingMiddleware(rate_limit=3))
    # Регистрируется последним — выполняется первым: удалить сообщение до остальных middleware/хендлеров.
    up_router.message.middleware(DeleteUserMessageMiddleware())
    up_router.include_routers(*routers)