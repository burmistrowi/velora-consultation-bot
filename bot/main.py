import asyncio
import logging
from aiogram import Bot, Dispatcher, Router
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from bot.misc.env import settings
from bot.handlers.main import register_all_handlers
from bot.database.models import register_models
from bot.database.main import Database
from bot.database.migrations import (
    migrate_drop_time_slots_price,
    migrate_add_booking_meta_charged_amount,
    migrate_add_booking_meta_client_fields,
    migrate_booking_meta_reschedule_fields,
    migrate_add_time_slots_service_id,
    migrate_add_time_slots_confirmation_fields,
    migrate_time_slots_business_and_uniques,
    migrate_create_booking_reschedules,
    migrate_support_schema,
    migrate_schedule_templates,
    migrate_template_rules_break_minutes,
)
from bot.services import setup_services

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main() -> None:
    """
    Initializes and starts the bot, setting up web server and handler registration.
    """
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    try:
        # Register bot handlers
        logger.info("Registering bot handlers...")
        main_router = Router()
        await register_all_handlers(main_router, bot=bot)
        dp.include_router(main_router)

        # Database init (creates tables if needed)
        await register_models()
        db = Database()
        # Lightweight runtime migrations (safe, idempotent)
        migrate_drop_time_slots_price(db.engine)
        migrate_add_booking_meta_charged_amount(db.engine)
        migrate_add_booking_meta_client_fields(db.engine)
        migrate_booking_meta_reschedule_fields(db.engine)
        migrate_add_time_slots_service_id(db.engine)
        migrate_add_time_slots_confirmation_fields(db.engine)
        migrate_time_slots_business_and_uniques(db.engine)
        migrate_create_booking_reschedules(db.engine)
        migrate_support_schema(db.engine)
        migrate_schedule_templates(db.engine)
        migrate_template_rules_break_minutes(db.engine)
        Database.BASE.metadata.create_all(db.engine)

        # Initialize services
        logger.info("Setting up services...")
        await setup_services(bot)

        if settings.BOT_RUN_MODE.lower() == "webhook":
            if not settings.WEBHOOK_URL:
                raise ValueError("WEBHOOK_URL is required when BOT_RUN_MODE=webhook")

            webhook_path = settings.WEB_WEBHOOK_PATH
            await bot.set_webhook(f"{settings.WEBHOOK_URL.rstrip('/')}{webhook_path}")

            app = web.Application()
            SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
            setup_application(app, dp, bot=bot)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, settings.WEB_HOST, settings.WEB_PORT)
            logger.info(f"Starting webhook server on {settings.WEB_HOST}:{settings.WEB_PORT}{webhook_path}")
            await site.start()

            # keep running
            await asyncio.Event().wait()
        else:
            # Start polling
            logger.info("Starting bot polling...")
            # If webhook was set ранее, polling может вести себя неожиданно.
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        await bot.session.close()

    finally:
        # Ensure bot session closes when program ends
        await bot.session.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
