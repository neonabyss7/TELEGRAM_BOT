#!/usr/bin/env python3
import asyncio
import logging
import os
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("upload_data_log.txt")
    ]
)
logger = logging.getLogger("upload_data")

# Импортируем необходимые модули из проекта
from src.database.db_handler import init_db, disconnect_db
from src.utils.message_filters import is_message_valid
from src.utils.text_generator import update_markov_model
from src.database.db_handler import save_filtered_message

# Константы
INPUT_FILE = "data.txt"
# Информация о виртуальном пользователе (используется для логов и базы данных)
VIRTUAL_USER_ID = 999999
VIRTUAL_USERNAME = "data_uploader"
VIRTUAL_FIRST_NAME = "Data"
VIRTUAL_LAST_NAME = "Uploader"
VIRTUAL_CHAT_ID = VIRTUAL_USER_ID  # Используем ID пользователя в качестве ID чата


async def process_file(file_path):
    """
    Обрабатывает файл data.txt аналогично команде /if
    Фильтрует сообщения и добавляет их в базу данных
    """
    logger.info(f"Начата обработка файла: {file_path}")
    
    # Проверяем существование файла
    if not os.path.exists(file_path):
        logger.error(f"Файл не найден: {file_path}")
        return False, f"Файл не найден: {file_path}", None
    
    try:
        # Статистика
        total_lines = 0
        valid_lines = 0
        
        # Инициализируем соединение с базой данных
        await init_db()
        logger.info("Соединение с базой данных установлено")
        
        # Открываем файл и обрабатываем строки
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                total_lines += 1
                line = line.strip()
                
                # Пропускаем пустые строки
                if not line:
                    continue
                
                # Фильтруем строку
                if is_message_valid(line):
                    # Добавляем строку в базу данных
                    await save_filtered_message(
                        VIRTUAL_USER_ID,
                        VIRTUAL_USERNAME,
                        VIRTUAL_FIRST_NAME,
                        VIRTUAL_LAST_NAME,
                        line,
                        VIRTUAL_CHAT_ID
                    )
                    valid_lines += 1
                    
                    # Логируем каждые 100 обработанных строк
                    if valid_lines % 100 == 0:
                        logger.info(f"Обработано {total_lines} строк, добавлено в базу {valid_lines}")
        
        # Формируем статистику
        stats = {
            "total_lines": total_lines,
            "valid_lines": valid_lines,
            "invalid_lines": total_lines - valid_lines,
            "file_name": os.path.basename(file_path),
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Обновляем модель Маркова
        logger.info("Обновляем модель Маркова с новыми данными...")
        await update_markov_model()
        logger.info("Модель Маркова успешно обновлена")
        
        # Закрываем соединение с базой данных
        await disconnect_db()
        logger.info("Соединение с базой данных закрыто")
        
        result_message = (
            f"Файл успешно обработан.\n"
            f"Всего строк: {stats['total_lines']}\n"
            f"Добавлено в базу: {stats['valid_lines']}\n"
            f"Отфильтровано: {stats['invalid_lines']}"
        )
        
        logger.info(result_message.replace('\n', ' | '))
        return True, result_message, stats
    
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}", exc_info=True)
        return False, f"Ошибка при обработке файла: {e}", None
    finally:
        # Закрываем соединение с базой данных в любом случае
        try:
            await disconnect_db()
            logger.info("Соединение с базой данных закрыто")
        except:
            pass


async def main():
    """
    Основная функция скрипта
    """
    logger.info("=" * 50)
    logger.info("Запуск скрипта upload_data.py")
    logger.info("=" * 50)
    
    try:
        # Обрабатываем файл data.txt
        success, message, stats = await process_file(INPUT_FILE)
        
        if success:
            logger.info("=" * 50)
            logger.info(f"Обработка завершена успешно")
            logger.info(f"Всего строк: {stats['total_lines']}")
            logger.info(f"Добавлено в базу: {stats['valid_lines']}")
            logger.info(f"Отфильтровано: {stats['invalid_lines']}")
            logger.info("=" * 50)
        else:
            logger.error("=" * 50)
            logger.error(f"Обработка не удалась: {message}")
            logger.error("=" * 50)
    
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)


if __name__ == "__main__":
    # Запускаем асинхронную обработку
    asyncio.run(main())