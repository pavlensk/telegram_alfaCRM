#!/usr/bin/env python3
"""
Спортивный Telegram-бот (плавание, бег, триатлон).
Главная точка входа: инициализирует все модули и запускает бот + веб-сервер.
"""

import asyncio
import signal
import logging
import time
from typing import Dict

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

import config
from resources.loader import initialize_resources
from core.crm_client import AlfaCRMClient
from infrastructure.web_server import start_web_app
from handlers import setup_all_handlers

# ---- Setup logging ----

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- Bot state and handlers ----


async def notify_bot_ready(bot: Bot):
    """Отправляет уведомление о запуске бота."""
    if not config.BOT_STATUS_CHAT_ID:
        logger.info("BOT_STATUS_CHAT_ID не задан, пропускаем уведомление")
        return
    
    try:
        await bot.send_message(
            config.BOT_STATUS_CHAT_ID,
            f"🤖 <b>Sports Bot запущен!</b>\n\n"
            f"🕐 {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"✅ AlfaCRM: OK\n"
            f"✅ Web: порт {config.PORT}",
            parse_mode="HTML"
        )
        logger.info("✅ Уведомление о запуске отправлено!")
    except Exception as e:
        logger.error(f"❌ Ошибка уведомления о запуске: {type(e).__name__}: {e}")


async def notify_bot_stopped(bot: Bot):
    """Отправляет уведомление об остановке бота."""
    if not config.BOT_STATUS_CHAT_ID:
        return
    
    try:
        await bot.send_message(
            config.BOT_STATUS_CHAT_ID,
            "🛑 <b>Sports Bot остановлен</b>",
            parse_mode="HTML"
        )
        logger.info("✅ Уведомление об остановке отправлено!")
    except Exception as e:
        logger.error(f"❌ Ошибка уведомления об остановке: {type(e).__name__}: {e}")


async def run_bot(bot: Bot) -> None:
    """Запускает Telegram-бота с диспетчером."""
    dp = Dispatcher()
    
    # Инициализируем AlfaCRM клиент
    alfa = AlfaCRMClient(config.ALFA_EMAIL, config.ALFA_API_KEY)
    
    # Состояние: menu_msg_id_by_user[uid] = message_id последнего меню
    menu_msg_id_by_user: Dict[int, int] = {}
    
    # Состояние: waiting_phone_section_by_user[uid] = section или None
    waiting_phone_section_by_user: Dict[int, config.Section] = {}
    
    # Состояние квиза: quiz_state[uid] = {"question_idx": int, "score": int, "timestamp": float}
    quiz_state: Dict[int, Dict] = {}
    
    # Регистрируем все хендлеры
    setup_all_handlers(
        dp,
        menu_msg_id_by_user,
        waiting_phone_section_by_user,
        quiz_state,
        alfa
    )
    
    # Отправляем уведомление о запуске
    await notify_bot_ready(bot)
    
    logger.info("🚀 Starting Telegram bot polling...")
    
    # Запускаем polling
    await dp.start_polling(bot)


async def main():
    """Главная асинхронная функция."""
    bot = Bot(config.BOT_TOKEN)
    
    # Запускаем бота и веб-сервер параллельно
    bot_task = asyncio.create_task(run_bot(bot))
    web_task = asyncio.create_task(start_web_app())
    
    def handle_shutdown():
        """Обработчик сигналов выключения."""
        logger.info("⚠️ Shutdown signal received...")
        bot_task.cancel()
        web_task.cancel()
    
    # Регистрируем обработчики сигналов
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_shutdown)
    
    try:
        await asyncio.gather(bot_task, web_task)
    except asyncio.CancelledError:
        logger.info("Tasks cancelled")
    finally:
        await notify_bot_stopped(bot)
        await bot.session.close()
        logger.info("✅ Bot session closed")


if __name__ == "__main__":
    # Инициализируем ресурсы перед запуском бота
    try:
        initialize_resources()
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {type(e).__name__}: {e}")
        raise
