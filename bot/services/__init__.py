"""
Модуль для инициализации сервисов
"""

async def setup_services(bot):
    """
    Инициализация всех сервисов после создания бота
    """
    from bot.misc.scheduler import setup_reminders
    setup_reminders(bot)