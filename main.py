import asyncio
import logging
import os
import signal
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Импортируем конфигурационные данные
from src.config import BOT_TOKEN, ALLOWED_GROUP_CHAT_ID, ADMIN_USER_ID

# Импортируем базу данных и обработчики
from src.database.db_handler import init_db
from src.handlers.message_handlers import register_message_handlers
from src.handlers.command_handlers import register_command_handlers
from src.utils.text_generator import update_markov_model

# Создаем директорию для логов, если она не существует
os.makedirs("src/logs", exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("src/logs/bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Глобальные переменные для доступа к боту и диспетчеру из обработчика сигналов
bot = None
dp = None

# Флаг для отслеживания процесса завершения работы
is_shutting_down = False

async def shutdown(signal_type=None):
    """
    Корректное завершение работы бота
    """
    global is_shutting_down
    
    if is_shutting_down:
        return
        
    is_shutting_down = True
    logger.info(f"Получен сигнал на завершение работы: {signal_type}")
    
    if dp:
        logger.info("Останавливаем опрос Telegram API...")
        await dp.stop_polling()
    
    # Закрываем соединение с базой данных
    from src.database.db_handler import disconnect_db
    await disconnect_db()
    
    # Отправляем сообщение админу о завершении работы, если это не тестовый запуск
    if bot and ADMIN_USER_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_USER_ID, 
                text="🛑 Бот завершает работу. Служба будет недоступна до следующего запуска."
            )
            logger.info(f"Отправлено уведомление о завершении работы администратору (ID: {ADMIN_USER_ID})")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о завершении работы: {e}")
    
    logger.info("Бот успешно завершил работу")

def register_signals():
    """
    Регистрация обработчиков сигналов завершения для корректного завершения работы
    """
    for sig_name in ('SIGINT', 'SIGTERM', 'SIGABRT'):
        try:
            sig = getattr(signal, sig_name)
            asyncio.get_event_loop().add_signal_handler(
                sig, 
                lambda s=sig_name: asyncio.create_task(shutdown(s))
            )
            logger.info(f"Зарегистрирован обработчик для сигнала {sig_name}")
        except (NotImplementedError, AttributeError, ValueError) as ex:
            logger.warning(f"Не удалось зарегистрировать обработчик для сигнала {sig_name}: {ex}")
    
    logger.info("Система обработки сигналов завершения настроена")

async def main():
    """
    Main function to start the Telegram bot
    """
    global bot, dp
    
    # Создаем директорию для данных, если она не существует
    os.makedirs("data", exist_ok=True)
    
    try:
        # Initialize bot with token
        # Используем новый синтаксис для aiogram 3.7.0+
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        
        # Регистрируем обработчики сигналов для корректного завершения
        register_signals()
        
        # Initialize database
        await init_db()
        
        # Update Markov model based on messages in database
        await update_markov_model()
        
        # Register all message handlers
        register_message_handlers(dp)
        
        # Register all command handlers
        register_command_handlers(dp)
        
        # Не отправляем сообщения о запуске по требованию пользователя
        # Бот должен отвечать только на команды
        
        # Start the bot with skip_updates=True чтобы игнорировать сообщения, 
        # полученные во время простоя бота
        logger.info("Бот запущен и готов к работе")
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        await shutdown("CRITICAL_ERROR")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен через KeyboardInterrupt или SystemExit")
    except Exception as e:
        logger.critical(f"Необработанное исключение: {e}", exc_info=True)