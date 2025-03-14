from aiogram import Dispatcher, Bot
from aiogram.types import Message, FSInputFile, BufferedInputFile
from aiogram.filters import Command

import asyncio
import logging
import os
import random
from datetime import datetime

# Глобальная переменная для хранения времени запуска бота
BOT_START_TIME = datetime.now().timestamp()
from src.utils.text_generator import generate_sentence, generate_sentence_custom, generate_story
from src.utils.file_processor import download_and_process_file
from src.utils.text_generator import update_markov_model
from src.database.db_handler import get_random_sticker_from_db, get_random_animation_from_db, get_database_stats, get_all_messages
from src.utils.image_processor import create_meme, create_atmta_image, create_demotivator, create_jpeg_artifact
from src.utils.access_control import check_chat_access, process_group_member, check_admin_rights, manually_add_user, manually_remove_user

from src.config import ALLOWED_GROUP_CHAT_ID, ADMIN_USER_ID

logger = logging.getLogger(__name__)

# Вспомогательная функция для проверки времени сообщения
def is_message_outdated(message: Message) -> bool:
    """
    Проверяет, устарело ли сообщение (было отправлено до запуска бота)
    
    Args:
        message (Message): Сообщение для проверки
        
    Returns:
        bool: True если сообщение устарело, False в противном случае
    """
    message_time = message.date.timestamp()
    # Если сообщение было отправлено до запуска бота, считаем его устаревшим
    if message_time < BOT_START_TIME:
        logger.info(f"Игнорирую устаревшее сообщение от {message.from_user.id}, отправленное в {message.date}")
        return True
    return False

# Декоратор для проверки возраста сообщения в обработчиках команд
def check_message_age(handler):
    """
    Декоратор, который проверяет возраст сообщения перед вызовом обработчика команды.
    Если сообщение устарело (отправлено до запуска бота), обработчик не вызывается.
    
    Args:
        handler: Обработчик команды для декорирования
        
    Returns:
        Декорированный обработчик
    """
    async def wrapper(message: Message, *args, **kwargs):
        # Проверяем время сообщения
        if is_message_outdated(message):
            # Если сообщение устарело, игнорируем его
            return
        
        # Удаляем аргументы, которые не принимает обработчик
        # Фильтруем системные аргументы, такие как dispatcher, router и т.д.
        # для совместимости с aiogram
        handler_args = {}
        if kwargs:
            import inspect
            sig = inspect.signature(handler)
            for param in sig.parameters:
                if param in kwargs:
                    handler_args[param] = kwargs[param]
        
        # Иначе вызываем оригинальный обработчик только с ожидаемыми аргументами
        return await handler(message, *args, **handler_args)
    return wrapper

async def cmd_update_markov_realtime(message: Message):
    """
    Скрытая административная команда /mr (Markov Realtime) для обновления 
    цепей Маркова в реальном времени
    Доступна только для главного администратора
    """
    # Проверяем, что команда вызвана главным администратором
    if message.from_user.id != ADMIN_USER_ID:
        # Игнорируем команду если вызвана не администратором
        # Не отвечаем на команду, чтобы не раскрывать её существование
        logger.warning(f"Попытка несанкционированного доступа к скрытой команде /mr от пользователя {message.from_user.id}")
        return
    
    try:
        # Отправляем уведомление о начале обновления
        sent_message = await message.answer("🔄 <b>Начато обновление цепей Маркова в реальном времени...</b>")
        
        # Запускаем обновление модели Маркова
        start_time = datetime.now()
        await update_markov_model()
        end_time = datetime.now()
        
        # Вычисляем время выполнения
        execution_time = (end_time - start_time).total_seconds()
        
        # Отправляем сообщение об успешном обновлении
        await sent_message.edit_text(
            f"✅ <b>Цепи Маркова успешно обновлены!</b>\n\n"
            f"⏱️ Время выполнения: {execution_time:.2f} секунд"
        )
        
        logger.info(f"Администратор {message.from_user.id} выполнил команду /mr - обновление цепей Маркова в реальном времени")
        
        # Ждем 3 секунды перед удалением сообщений
        await asyncio.sleep(3)
        
        # Удаляем сообщение с результатом выполнения
        try:
            await sent_message.delete()
            logger.info("Удалено сообщение с результатом выполнения команды /mr")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с результатом: {e}")
        
        # Удаляем команду от пользователя
        try:
            await message.delete()
            logger.info("Удалена команда /mr от пользователя")
        except Exception as e:
            logger.error(f"Не удалось удалить команду /mr от пользователя: {e}")
        
    except Exception as e:
        # В случае ошибки
        await message.answer(f"❌ <b>Ошибка при обновлении цепей Маркова:</b>\n<code>{str(e)}</code>")
        logger.error(f"Ошибка при выполнении команды /mr: {e}", exc_info=True)

@check_message_age
async def cmd_generate_message(message: Message):
    """
    Handle the /gm command - generate a single message using Markov chains
    """
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    
    logger.info(f"User {user_id} запросил генерацию сообщения через команду /gm")
    
    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, user_id)
    if not has_access:
        logger.warning(f"Access denied for chat {chat_id}, user {user_id} (command: /gm)")
        return
    
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    try:
        # Генерируем простое предложение, без использования потоков
        logger.info("Генерируем текст напрямую, без executor")
        # Используем простую реализацию
        generated_text = generate_sentence_custom(min_words=5, max_words=20)
        
        logger.info(f"Сгенерированный текст: {generated_text}")
        
        # Проверяем, не пустой ли текст
        if not generated_text:
            generated_text = "К сожалению, не удалось сгенерировать текст. Пожалуйста, попробуйте ещё раз."
            logger.warning("Сгенерирован пустой текст")
        
        # Отправляем ответ
        logger.info(f"Пытаемся отправить ответ пользователю {user_id}")
        await message.answer(generated_text)
        logger.info(f"Успешно отправлено сгенерированное сообщение пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /gm: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при генерации сообщения. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

@check_message_age
async def cmd_generate_story(message: Message):
    """
    Handle the /story command - generate a story using Markov chains
    Supports parameters: /story 3 (generates a story with 3 sentences)
    """
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    
    logger.info(f"User {user_id} запросил генерацию истории через команду /story")
    
    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, user_id)
    if not has_access:
        logger.warning(f"Access denied for chat {chat_id}, user {user_id} (command: /story)")
        return
    
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    try:
        # Пробуем получить параметры из сообщения
        command_args = message.text.split()
        num_sentences = 3  # Устанавливаем фиксированное количество предложений для упрощения
        
        # Если пользователь указал количество предложений
        if len(command_args) > 1:
            try:
                user_sentences = int(command_args[1])
                if 1 <= user_sentences <= 5:  # Ограничиваем до 5 предложений для стабильности
                    num_sentences = user_sentences
                    logger.info(f"Установлено пользовательское количество предложений: {num_sentences}")
                else:
                    logger.info(f"Некорректное количество предложений ({user_sentences}), использую значение по умолчанию")
            except ValueError:
                logger.info("Некорректный формат числа предложений, использую значение по умолчанию")
        
        # Генерируем историю напрямую, без использования потоков
        logger.info(f"Генерируем историю напрямую, {num_sentences} предложений")
        
        # Создаем историю из нескольких предложений
        sentences = []
        for _ in range(num_sentences):
            sentence = generate_sentence_custom(min_words=5, max_words=15)
            sentences.append(sentence)
        
        generated_story = " ".join(sentences)
        
        logger.info(f"Сгенерирована история: {generated_story}")
        
        # Проверяем, не пустая ли история
        if not generated_story:
            generated_story = "К сожалению, не удалось сгенерировать историю. Пожалуйста, попробуйте ещё раз."
            logger.warning("Сгенерирована пустая история")
        
        # Отправляем ответ
        logger.info(f"Пытаемся отправить историю пользователю {user_id}")
        await message.answer(generated_story)
        logger.info(f"Успешно отправлена сгенерированная история пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /story: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при генерации истории. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

async def cmd_import_file(message: Message):
    """
    Handle the /if command - import messages from a text file
    Each line in the file will be processed as a separate message
    """
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    
    logger.info(f"User {user_id} запросил импорт сообщений через команду /if")
    
    # Эта команда должна работать только в приватном чате
    if chat_id > 0:
        # Проверка, есть ли пользователь в списке разрешенных
        has_access = await check_chat_access(chat_id, user_id)
        if not has_access:
            logger.warning(f"Access denied for user {user_id} (command: /if)")
            return
    else:
        # Для групповых чатов команда недоступна
        logger.warning(f"Command /if is not available in group chats")
        await message.answer("Команда /if доступна только в приватном чате с ботом.")
        return
    
    try:
        # Проверяем, есть ли прикрепленный файл
        if not message.document:
            await message.answer("Пожалуйста, прикрепите текстовый файл (.txt) к команде /if")
            logger.info("Пользователь не прикрепил файл к команде /if")
            return
            
        # Получаем информацию о пользователе для сохранения в базу данных
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        chat_id = message.chat.id
        
        # Получаем экземпляр бота
        bot = message.bot
        
        # Загружаем и обрабатываем файл
        success, result_message, stats = await download_and_process_file(
            message.document, bot, user_id, username, first_name, last_name, chat_id
        )
        
        if success and stats:
            # Формируем подробный ответ со статистикой
            response = (
                f"Файл успешно обработан.\n"
                f"Всего строк: {stats['total_lines']}\n"
                f"Добавлено в базу: {stats['valid_lines']}\n"
                f"Отфильтровано: {stats['invalid_lines']}"
            )
            
            # Обновляем модель Маркова с новыми данными
            await update_markov_model()
            logger.info("Модель Маркова обновлена после импорта файла")
            
            await message.answer(response)
            logger.info(f"Файл успешно обработан. Добавлено {stats['valid_lines']} сообщений")
        else:
            await message.answer(result_message)
            logger.warning(f"Ошибка при обработке файла: {result_message}")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /if: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при обработке файла. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)
            
async def cmd_send_random_sticker(message: Message):
    """
    Handle the /sst command - send a random sticker from the database
    """
    user_id = message.from_user.id
    logger.info(f"User {user_id} запросил случайный стикер через команду /sst")
    
    try:
        # Получаем случайный стикер из базы данных
        sticker_file_id = await get_random_sticker_from_db()
        
        if sticker_file_id:
            # Отправляем стикер
            await message.answer_sticker(sticker_file_id)
            logger.info(f"Отправлен случайный стикер пользователю {user_id}")
        else:
            # Если стикеров нет в базе
            await message.answer("В базе данных пока нет стикеров. Пришлите стикеры в чат, чтобы я мог их запомнить!")
            logger.info("В базе данных нет стикеров")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /sst: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при отправке стикера. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)
            
async def cmd_send_random_animation(message: Message):
    """
    Handle the /sg command - send a random GIF animation from the database
    """
    user_id = message.from_user.id
    logger.info(f"User {user_id} запросил случайную GIF-анимацию через команду /sg")
    
    try:
        # Получаем случайную GIF-анимацию из базы данных
        animation_file_id = await get_random_animation_from_db()
        
        if animation_file_id:
            # Отправляем анимацию
            await message.answer_animation(animation_file_id)
            logger.info(f"Отправлена случайная GIF-анимация пользователю {user_id}")
        else:
            # Если GIF-анимаций нет в базе
            await message.answer("В базе данных пока нет GIF-анимаций. Пришлите GIF-анимации в чат, чтобы я мог их запомнить!")
            logger.info("В базе данных нет GIF-анимаций")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /sg: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при отправке GIF-анимации. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)
            
async def cmd_mem_with_reply(message: Message):
    """
    Handle the /mem command with replied photo
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.info(f"User {user_id} запросил создание мема через команду /mem с ответом на фото в чате {chat_id}")
    
    # Проверяем доступ
    if not await check_chat_access(chat_id, user_id):
        logger.warning(f"Отказано в доступе пользователю {user_id} в чате {chat_id}")
        # Не отвечаем на сообщение, чтобы не создавать шум в неразрешенных чатах
        return
    
    try:
        # Проверяем, есть ли родительское сообщение (reply)
        if not message.reply_to_message or not message.reply_to_message.photo:
            await message.answer("Для создания мема ответьте на сообщение с фотографией командой /mem")
            logger.info("Пользователь не ответил на сообщение с фото командой /mem")
            return
        
        # Получаем фото из родительского сообщения
        photo = message.reply_to_message.photo
        logger.info("Обнаружено фото в родительском сообщении")
        
        # Генерируем текст для мема
        meme_text = generate_sentence_custom(min_words=5, max_words=15)
        logger.info(f"Сгенерирован текст для мема: {meme_text}")
        
        if not meme_text:
            meme_text = "Когда забыл текст для мема"
            logger.warning("Сгенерирован пустой текст для мема, используется запасной вариант")
        
        # Получаем экземпляр бота
        bot = message.bot
        
        # Берем фото с наивысшим разрешением (последнее в списке)
        photo_obj = photo[-1]
        file_info = await bot.get_file(photo_obj.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        
        logger.info(f"Загружено изображение для мема, file_id: {photo_obj.file_id}")
        
        # Создаем мем
        meme_bytes = await create_meme(downloaded_file.read(), meme_text)
        
        if meme_bytes:
            # Отправляем мем (без подписи)
            await message.answer_photo(
                photo=BufferedInputFile(
                    meme_bytes, 
                    filename="meme.jpg"
                )
            )
            logger.info(f"Мем успешно создан и отправлен пользователю {user_id}")
        else:
            await message.answer("Не удалось создать мем. Возможно, формат изображения не поддерживается.")
            logger.warning("Не удалось создать мем из изображения")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /mem: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при создании мема. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

async def cmd_create_meme(message: Message):
    """
    Handle the /mem command when used with a caption on a photo
    Работает с двумя форматами:
    1. Фото с подписью /mem
    2. Команда /mem в ответ на сообщение с фото
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    logger.info(f"User {user_id} запросил создание мема через команду /mem в чате {chat_id}")
    
    # Проверяем доступ
    if not await check_chat_access(chat_id, user_id):
        logger.warning(f"Отказано в доступе пользователю {user_id} в чате {chat_id}")
        # Не отвечаем на сообщение, чтобы не создавать шум в неразрешенных чатах
        return
        
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    try:
        # Определяем источник фотографии
        photo_file_id = None
        
        # Если у сообщения есть фото, значит команда была в подписи к фото
        if message.photo:
            logger.info("Обнаружено фото с подписью /mem")
            # Берем последнее (наилучшее качество) фото
            photo_file_id = message.photo[-1].file_id
            logger.info(f"ID фото для мема: {photo_file_id}")
        # Если это ответ на сообщение с фото
        elif message.reply_to_message and message.reply_to_message.photo:
            logger.info("Обнаружен ответ на сообщение с фото")
            # Перенаправляем на обработчик для ответа на фото
            return await cmd_mem_with_reply(message)
        else:
            await message.answer("Для создания мема используйте один из форматов:\n"
                               "1. Отправьте фото с подписью /mem\n"
                               "2. Ответьте на сообщение с фото командой /mem")
            logger.info("Пользователь не прикрепил фото к команде /mem")
            return
        
        # Генерируем текст для мема
        meme_text = generate_sentence_custom(min_words=5, max_words=15)
        logger.info(f"Сгенерирован текст для мема: {meme_text}")
        
        if not meme_text:
            meme_text = "Когда забыл текст для мема"
            logger.warning("Сгенерирован пустой текст для мема, используется запасной вариант")
        
        # Получаем экземпляр бота
        bot = message.bot
        
        # Загружаем фото и создаём мем
        file_info = await bot.get_file(photo_file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        
        logger.info(f"Загружено изображение для мема, file_id: {photo_file_id}")
        
        # Создаем мем
        meme_bytes = await create_meme(downloaded_file.read(), meme_text)
        
        if meme_bytes:
            # Отправляем мем (без подписи)
            await message.answer_photo(
                photo=BufferedInputFile(
                    meme_bytes, 
                    filename="meme.jpg"
                )
            )
            logger.info(f"Мем успешно создан и отправлен пользователю {user_id}")
        else:
            await message.answer("Не удалось создать мем. Возможно, формат изображения не поддерживается.")
            logger.warning("Не удалось создать мем из изображения")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /mem: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при создании мема. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

async def cmd_help(message: Message):
    """
    Handle the /help command - show available commands and their descriptions
    """
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    
    logger.info(f"User {user_id} запросил помощь через команду /help")
    
    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, user_id)
    if not has_access:
        logger.warning(f"Access denied for chat {chat_id}, user {user_id} (command: /help)")
        return
    
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    try:
        help_text = """
<b>Команды бота:</b>

/gm - сгенерировать случайное сообщение
/story [число] - сгенерировать историю (по умолчанию 3 предложения)

/mem - создать мем (ответом на фото или с подписью к фото)
/at - создать АТМТА-эффект (ответом на фото или с подписью к фото)
/dem - создать демотиватор (ответом на фото или с подписью к фото)
/jp - добавить JPEG-артефакты (ответом на фото или с подписью к фото)


/sst - отправить случайный стикер
/sg - отправить случайную GIF-анимацию
/stats - показать статистику базы данных
/delmsg - удалить сообщение бота (в ответ на сообщение)
"""
        await message.answer(help_text, parse_mode="HTML")
        logger.info(f"Информация о командах отправлена пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /help: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при выводе справки. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

async def cmd_admin_help(message: Message):
    """
    Handle the /help2 command - show administrative commands
    This is an administrative command that can only be used in private chat
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    logger.info(f"User {user_id} запросил административную помощь через команду /help2")
    
    # Проверяем, что команда используется в приватном чате
    if chat_id < 0:
        logger.warning(f"Отказано в доступе к команде /help2 в групповом чате {chat_id}")
        await message.answer("Эта команда доступна только в приватном чате с ботом.")
        return
        
    # Проверяем, что пользователь является администратором
    is_admin = await check_admin_rights(user_id)
    if not is_admin:
        logger.warning(f"Отказано в доступе пользователю {user_id} для команды /help2 (не администратор)")
        await message.answer("Эта команда доступна только администраторам бота.")
        return
    
    try:
        admin_help_text = """
<b>Административные команды бота:</b>

/exp - экспортировать все сообщения из базы данных
/if - импортировать сообщения из текстового файла
/adduser ID [username] [name] [surname] - добавить пользователя вручную
/deluser ID - удалить пользователя из списка разрешенных

<b>Скрытые команды:</b>
/mr - обновление цепей Маркова в реальном времени (только для главного администратора)
"""
        await message.answer(admin_help_text, parse_mode="HTML")
        logger.info(f"Информация об административных командах отправлена пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /help2: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при выводе справки. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

async def cmd_export_messages(message: Message):
    """
    Handle the /exp command - export all messages from the database
    This is an administrative command that can only be used in private chat
    """
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    chat_type = message.chat.type
    logger.info(f"User {user_id} запросил экспорт сообщений через команду /exp в чате типа {chat_type}")
    
    # Проверка, что команда выполняется только в личном чате с ботом
    if chat_type != "private":
        logger.warning(f"Попытка использования административной команды /exp в непредназначенном для этого чате типа {chat_type}")
        await message.answer("Эта команда доступна только в приватном чате с ботом.")
        return
    
    # Проверка, есть ли пользователь в списке разрешенных
    has_access = await check_chat_access(chat_id, user_id)
    if not has_access:
        logger.warning(f"Access denied for user {user_id} (command: /exp)")
        return
        
    try:
        # Получаем все сообщения из базы данных
        messages = await get_all_messages()
        
        if not messages:
            await message.answer("В базе данных нет сообщений для экспорта.")
            logger.info("База данных пуста, нет сообщений для экспорта")
            return
            
        # Формируем текстовый файл
        text_content = "\n".join(messages)
        
        # Создаем файл для отправки
        from io import BytesIO
        file_obj = BytesIO(text_content.encode('utf-8'))
        
        # Отправляем файл пользователю
        await message.answer_document(
            document=BufferedInputFile(
                file_obj.getvalue(),
                filename="messages_export.txt"
            ),
            caption=f"Экспорт {len(messages)} сообщений из базы данных."
        )
        logger.info(f"Экспорт {len(messages)} сообщений успешно выполнен для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при экспорте сообщений: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при экспорте сообщений. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

async def cmd_stats(message: Message):
    """
    Handle the /stats command - show database statistics
    """
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    
    logger.info(f"User {user_id} запросил статистику через команду /stats")
    
    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, user_id)
    if not has_access:
        logger.warning(f"Access denied for chat {chat_id}, user {user_id} (command: /stats)")
        return
    
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    try:
        # Получаем статистику из базы данных
        stats = await get_database_stats()
        
        stats_text = f"""
📊 <b>Статистика базы данных:</b>

📝 Сообщений сохранено: <b>{stats['messages_count']}</b>
🔤 Уникальных слов: <b>{stats['unique_words_count']}</b>
😊 Стикеров в базе: <b>{stats['stickers_count']}</b>
🎬 GIF-анимаций в базе: <b>{stats['animations_count']}</b>
"""
        await message.answer(stats_text, parse_mode="HTML")
        logger.info(f"Статистика базы данных отправлена пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /stats: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при получении статистики. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

async def cmd_delete_message(message: Message):
    """
    Handle the /delmsg command - delete the message with the command and the replied message
    Работает только в ответ на сообщение бота, которое нужно удалить
    """
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    
    logger.info(f"User {user_id} запросил удаление сообщений через команду /delmsg")
    
    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, user_id)
    if not has_access:
        logger.warning(f"Access denied for chat {chat_id}, user {user_id} (command: /delmsg)")
        return
    
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    try:
        # Проверяем, является ли сообщение ответом на другое сообщение
        if not message.reply_to_message:
            logger.info(f"Команда /delmsg использована не в ответ на сообщение")
            await message.answer("Эта команда должна использоваться в ответ на сообщение, которое нужно удалить.")
            return
            
        # Удаляем сообщение бота, на которое был дан ответ
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id
            )
            logger.info(f"Удалено сообщение с ID {message.reply_to_message.message_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение бота: {e}")
            
        # Удаляем сообщение с командой
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id
            )
            logger.info(f"Удалено сообщение с командой с ID {message.message_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с командой: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /delmsg: {e}", exc_info=True)

async def cmd_create_atmta(message: Message):
    """
    Handle the /at command - create ATMTA (mirrored) image effect
    Работает с двумя форматами:
    1. Фото с подписью /at
    2. Команда /at в ответ на сообщение с фото
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    logger.info(f"User {user_id} запросил создание АТМТА-изображения через команду /at в чате {chat_id}")
    
    # Проверяем доступ
    if not await check_chat_access(chat_id, user_id):
        logger.warning(f"Отказано в доступе пользователю {user_id} в чате {chat_id}")
        # Не отвечаем на сообщение, чтобы не создавать шум в неразрешенных чатах
        return
        
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    try:
        # Определяем источник фотографии
        photo_file_id = None
        
        # Если у сообщения есть фото, значит команда была в подписи к фото
        if message.photo:
            logger.info("Обнаружено фото с подписью /at")
            # Берем последнее (наилучшее качество) фото
            photo_file_id = message.photo[-1].file_id
            logger.info(f"ID фото для АТМТА: {photo_file_id}")
        # Если это ответ на сообщение с фото
        elif message.reply_to_message and message.reply_to_message.photo:
            logger.info("Обнаружен ответ на сообщение с фото для создания АТМТА")
            # Получаем фото из родительского сообщения
            photo = message.reply_to_message.photo
            # Берем фото с наивысшим разрешением (последнее в списке)
            photo_file_id = photo[-1].file_id
            logger.info(f"ID фото из ответа для АТМТА: {photo_file_id}")
        else:
            await message.answer("Для создания АТМТА-изображения используйте один из форматов:\n"
                              "1. Отправьте фото с подписью /at\n"
                              "2. Ответьте на сообщение с фото командой /at")
            logger.info("Пользователь не прикрепил фото к команде /at")
            return
        
        # Получаем экземпляр бота
        bot = message.bot
        
        # Дополнительная проверка на случай ошибок
        if not photo_file_id:
            logger.error("Не удалось получить file_id фотографии")
            await message.answer("Ошибка при получении фотографии. Пожалуйста, попробуйте еще раз.")
            return
            
        try:
            # Загружаем фото и создаём АТМТА-изображение
            file_info = await bot.get_file(photo_file_id)
            downloaded_file = await bot.download_file(file_info.file_path)
            
            logger.info(f"Загружено изображение для АТМТА, file_id: {photo_file_id}")
            
            # Создаем АТМТА-изображение
            atmta_bytes = await create_atmta_image(downloaded_file.read())
            
            if atmta_bytes:
                # Отправляем АТМТА-изображение (без подписи)
                await message.answer_photo(
                    photo=BufferedInputFile(
                        atmta_bytes, 
                        filename="atmta.jpg"
                    )
                )
                logger.info(f"АТМТА-изображение успешно создано и отправлено пользователю {user_id}")
            else:
                await message.answer("Не удалось создать АТМТА-изображение. Возможно, формат изображения не поддерживается.")
                logger.warning("Не удалось создать АТМТА-изображение")
        except Exception as file_error:
            logger.error(f"Ошибка при загрузке или обработке файла: {file_error}", exc_info=True)
            await message.answer("Ошибка при обработке изображения. Пожалуйста, попробуйте другое фото.")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /at: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при создании АТМТА-изображения. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

async def cmd_jpeg_artifact(message: Message):
    """
    Handle the /jp command - create "deep-fried" image with JPEG artifacts and distortions
    Работает с двумя форматами:
    1. Фото с подписью /jp
    2. Команда /jp в ответ на сообщение с фото
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.info(f"User {user_id} запросил создание JPEG-артефактов через команду /jp в чате {chat_id}")
    
    # Проверяем доступ
    if not await check_chat_access(chat_id, user_id):
        logger.warning(f"Отказано в доступе пользователю {user_id} в чате {chat_id}")
        # Не отвечаем на сообщение, чтобы не создавать шум в неразрешенных чатах
        return
    
    try:
        bot = message.bot
        photo = None
        
        # Проверяем, является ли это сообщение с фото и командой в подписи
        if message.photo and message.caption and message.caption.startswith('/jp'):
            photo = message.photo
            logger.info("Получено фото с командой /jp в подписи")
        # Или это ответ на сообщение с фото
        elif message.reply_to_message and message.reply_to_message.photo:
            photo = message.reply_to_message.photo
            logger.info("Получено фото из родительского сообщения для команды /jp")
        
        if not photo:
            await message.answer("Для создания JPEG-артефактов нужно:\n"
                               "1. Прикрепить фото с подписью /jp, или\n"
                               "2. Ответить на сообщение с фото командой /jp")
            logger.info("Пользователь не предоставил фото для команды /jp")
            return
        
        # Отправляем индикатор "печатает...", чтобы пользователь знал, что запрос обрабатывается
        await message.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        
        # Берем фото с наивысшим разрешением (последнее в списке)
        photo_obj = photo[-1]
        file_info = await bot.get_file(photo_obj.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        
        # Случайный уровень "порчи" от 5 до 10 (более сильная порча)
        quality_level = random.randint(5, 10)
        logger.info(f"Выбран уровень 'порчи' изображения: {quality_level}")
        
        # Создаем "испорченное" изображение
        jpeg_artifact_bytes = await create_jpeg_artifact(downloaded_file, quality_level)
        
        # Создаем объект для загрузки в сообщение
        input_file = BufferedInputFile(
            jpeg_artifact_bytes,
            filename="jpeg_artifact.jpg"
        )
        
        # Отправляем результат без текста
        await message.answer_photo(input_file)
        logger.info(f"JPEG-артефакты успешно созданы и отправлены пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при создании JPEG-артефактов: {e}", exc_info=True)
        await message.answer("Произошла ошибка при создании JPEG-артефактов. Пожалуйста, попробуйте еще раз.")

async def cmd_create_demotivator(message: Message):
    """
    Handle the /dem command - create demotivator image
    Работает с двумя форматами:
    1. Фото с подписью /dem
    2. Команда /dem в ответ на сообщение с фото
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    logger.info(f"User {user_id} запросил создание демотиватора через команду /dem в чате {chat_id}")
    
    # Проверяем доступ
    if not await check_chat_access(chat_id, user_id):
        logger.warning(f"Отказано в доступе пользователю {user_id} в чате {chat_id}")
        # Не отвечаем на сообщение, чтобы не создавать шум в неразрешенных чатах
        return
        
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    try:
        # Определяем источник фотографии
        photo_file_id = None
        
        # Если у сообщения есть фото, значит команда была в подписи к фото
        if message.photo and len(message.photo) > 0:
            logger.info(f"Обнаружено фото с подписью /dem: {message.caption}")
            # Берем последнее (наилучшее качество) фото
            photo_file_id = message.photo[-1].file_id
            logger.info(f"ID фото для демотиватора: {photo_file_id}")
        # Если это ответ на сообщение с фото
        elif message.reply_to_message and message.reply_to_message.photo:
            logger.info("Обнаружен ответ на сообщение с фото для создания демотиватора")
            # Получаем фото из родительского сообщения
            photo = message.reply_to_message.photo
            # Берем фото с наивысшим разрешением (последнее в списке)
            photo_file_id = photo[-1].file_id
            logger.info(f"ID фото из ответа для демотиватора: {photo_file_id}")
        else:
            logger.warning(f"Не найдено фото для создания демотиватора: photo={bool(message.photo)}, len={len(message.photo) if message.photo else 0}, caption={message.caption}, reply={bool(message.reply_to_message)}")
            await message.answer("Для создания демотиватора используйте один из форматов:\n"
                              "1. Отправьте фото с подписью /dem\n"
                              "2. Ответьте на сообщение с фото командой /dem")
            logger.info("Пользователь не прикрепил фото к команде /dem")
            return
        
        # Получаем экземпляр бота
        bot = message.bot
        
        # Дополнительная проверка на случай ошибок
        if not photo_file_id:
            logger.error("Не удалось получить file_id фотографии")
            await message.answer("Ошибка при получении фотографии. Пожалуйста, попробуйте еще раз.")
            return
            
        try:
            # Загружаем фото и создаём демотиватор
            file_info = await bot.get_file(photo_file_id)
            downloaded_file = await bot.download_file(file_info.file_path)
            
            logger.info(f"Загружено изображение для демотиватора, file_id: {photo_file_id}")
            
            # Генерируем текст для демотиватора
            demo_text = generate_sentence_custom(min_words=2, max_words=6)
            logger.info(f"Сгенерирован текст для демотиватора: {demo_text}")
            
            # Создаем демотиватор
            demotivator_bytes = await create_demotivator(downloaded_file.read(), demo_text)
            
            if demotivator_bytes:
                # Отправляем демотиватор
                await message.answer_photo(
                    photo=BufferedInputFile(
                        demotivator_bytes, 
                        filename="demotivator.jpg"
                    )
                )
                logger.info(f"Демотиватор успешно создан и отправлен пользователю {user_id}")
            else:
                await message.answer("Не удалось создать демотиватор. Возможно, формат изображения не поддерживается.")
                logger.warning("Не удалось создать демотиватор из изображения")
        except Exception as file_error:
            logger.error(f"Ошибка при загрузке или обработке файла: {file_error}", exc_info=True)
            await message.answer("Ошибка при обработке изображения. Пожалуйста, попробуйте другое фото.")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /dem: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при создании демотиватора. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)


            
async def cmd_delete_user(message: Message):
    """
    Handle the /deluser command - manually remove a user from allowed users list
    This is an administrative command that can only be used in private chat
    Format: /deluser ID_пользователя
    Example: /deluser 123456789
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    logger.info(f"User {user_id} запросил удаление пользователя через команду /deluser в чате {chat_id}")
    
    # Проверяем, что команда используется в приватном чате
    if chat_id < 0:
        logger.warning(f"Отказано в доступе к команде /deluser в групповом чате {chat_id}")
        await message.answer("Эта команда доступна только в приватном чате с ботом.")
        return
        
    # Проверяем, что пользователь является администратором
    is_admin = await check_admin_rights(user_id)
    if not is_admin:
        logger.warning(f"Отказано в доступе пользователю {user_id} для команды /deluser (не администратор)")
        await message.answer("Эта команда доступна только администраторам бота.")
        return
    
    try:
        # Разбираем аргументы команды
        args = message.text.split()  # Разбиваем на части: /deluser, user_id
        
        # Проверяем, что указан ID пользователя
        if len(args) < 2:
            await message.answer(
                "Неверный формат команды. Используйте:\n"
                "/deluser ID_пользователя\n"
                "Пример: /deluser 123456789"
            )
            logger.warning("Неверный формат команды /deluser - не указан ID пользователя")
            return
            
        # Получаем ID пользователя
        try:
            target_user_id = int(args[1])
            if target_user_id <= 0:
                raise ValueError("ID пользователя должен быть положительным числом")
        except ValueError as e:
            await message.answer(f"Неверный ID пользователя: {args[1]}. ID должен быть числом больше нуля.")
            logger.warning(f"Неверный ID пользователя для команды /deluser: {args[1]} - {str(e)}")
            return
        
        # Проверяем, не пытается ли пользователь удалить администратора
        if target_user_id == ADMIN_USER_ID:
            await message.answer("Невозможно удалить администратора бота из списка разрешенных пользователей.")
            logger.warning(f"Попытка удалить администратора (ID: {target_user_id}) из списка разрешенных")
            return
        
        # Удаляем пользователя из базы данных
        success = await manually_remove_user(target_user_id)
        
        if success:
            await message.answer(f"Пользователь с ID {target_user_id} успешно удален из списка разрешенных.")
            logger.info(f"Администратор {user_id} удалил пользователя {target_user_id} из списка разрешенных")
        else:
            await message.answer(f"Не удалось удалить пользователя с ID {target_user_id}. Возможно, пользователь не найден в списке разрешенных.")
            logger.warning(f"Не удалось удалить пользователя {target_user_id} из списка разрешенных")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /deluser: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при удалении пользователя. Пожалуйста, попробуйте позже.")
            logger.info("Отправлено сообщение об ошибке")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

async def cmd_add_user(message: Message):
    """
    Handle the /adduser command - manually add a user to allowed users list
    This is an administrative command that can only be used in private chat
    Format: /adduser ID_пользователя [имя_пользователя] [имя] [фамилия]
    Example: /adduser 123456789 johndoe John Doe
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    logger.info(f"User {user_id} запросил добавление пользователя через команду /adduser в чате {chat_id}")
    
    # Проверяем, что команда используется в приватном чате
    if chat_id < 0:
        logger.warning(f"Отказано в доступе к команде /adduser в групповом чате {chat_id}")
        await message.answer("Эта команда доступна только в приватном чате с ботом.")
        return
        
    # Проверяем, что пользователь является администратором
    is_admin = await check_admin_rights(user_id)
    if not is_admin:
        logger.warning(f"Отказано в доступе пользователю {user_id} для команды /adduser (не администратор)")
        await message.answer("Эта команда доступна только администраторам бота.")
        return
    
    try:
        # Разбираем аргументы команды
        args = message.text.split(maxsplit=4)  # Максимум 4 части: /adduser, user_id, username, first_name, last_name
        
        # Проверяем, что указан хотя бы ID пользователя
        if len(args) < 2:
            await message.answer(
                "Неверный формат команды. Используйте:\n"
                "/adduser ID_пользователя [имя_пользователя] [имя] [фамилия]\n"
                "Пример: /adduser 123456789 johndoe John Doe"
            )
            logger.warning("Неверный формат команды /adduser - не указан ID пользователя")
            return
            
        # Получаем ID пользователя
        try:
            target_user_id = int(args[1])
            if target_user_id <= 0:
                raise ValueError("ID пользователя должен быть положительным числом")
        except ValueError as e:
            await message.answer(f"Неверный ID пользователя: {args[1]}. ID должен быть числом больше нуля.")
            logger.warning(f"Неверный ID пользователя для команды /adduser: {args[1]} - {str(e)}")
            return
            
        # Получаем дополнительные параметры (если указаны)
        username = args[2] if len(args) > 2 else None
        first_name = args[3] if len(args) > 3 else None
        last_name = args[4] if len(args) > 4 else None
        
        # Добавляем пользователя в базу данных
        success = await manually_add_user(target_user_id, username, first_name, last_name)
        
        if success:
            # Формируем информацию о добавленном пользователе
            user_info = f"ID: {target_user_id}"
            if username:
                user_info += f", Username: @{username}"
            if first_name:
                user_info += f", Имя: {first_name}"
            if last_name:
                user_info += f", Фамилия: {last_name}"
                
            await message.answer(f"Пользователь успешно добавлен в список разрешенных:\n{user_info}")
            logger.info(f"Администратор {user_id} добавил пользователя {target_user_id} в список разрешенных")
        else:
            await message.answer("Не удалось добавить пользователя. Проверьте правильность данных и попробуйте снова.")
            logger.warning(f"Не удалось добавить пользователя {target_user_id} через команду /adduser")
            
    except Exception as e:
        logger.error(f"Ошибка при добавлении пользователя: {e}", exc_info=True)
        await message.answer("Произошла ошибка при добавлении пользователя. Пожалуйста, попробуйте позже.")
        logger.info("Отправлено сообщение об ошибке")

def register_command_handlers(dp: Dispatcher):
    """Register all command handlers"""
    # Регистрируем только разрешенные команды для бота
    try:
        # Скрытая команда для обновления цепей Маркова (доступна только для главного администратора)
        dp.message.register(check_message_age(cmd_update_markov_realtime), Command("mr"))
        logger.info("Зарегистрирован скрытый обработчик для административной команды /mr")
        
        # Только разрешенные команды для генерации текста
        dp.message.register(check_message_age(cmd_generate_message), Command("gm"))
        logger.info("Зарегистрирован обработчик для команды /gm")
        
        dp.message.register(check_message_age(cmd_generate_story), Command("story"))
        logger.info("Зарегистрирован обработчик для команды /story")
        
        dp.message.register(check_message_age(cmd_import_file), Command("if"))
        logger.info("Зарегистрирован обработчик для команды /if")
        
        dp.message.register(check_message_age(cmd_send_random_sticker), Command("sst"))
        logger.info("Зарегистрирован обработчик для команды /sst")
        
        dp.message.register(check_message_age(cmd_send_random_animation), Command("sg"))
        logger.info("Зарегистрирован обработчик для команды /sg")
        
        # Регистрируем обработчик для команды /mem
        # 1. Для сообщений с фото и подписью /mem (Регистрируем в первую очередь, чтобы перехватывать до Command("mem"))
        # Создаем комбинированный фильтр для сообщений с фото и командой /mem в тексте
        dp.message.register(
            check_message_age(cmd_create_meme), 
            lambda message: message.photo and message.caption and message.caption.startswith('/mem')
        )
        
        # 2. Для текстовых сообщений с командой /mem (ответ на фото)
        dp.message.register(check_message_age(cmd_create_meme), Command("mem"))
        
        logger.info("Зарегистрирован обработчик для команды /mem")
        
        # Регистрируем обработчик для команды /at (АТМТА)
        # 1. Для сообщений с фото и подписью /at (Регистрируем в первую очередь, чтобы перехватывать до Command("at"))
        dp.message.register(
            check_message_age(cmd_create_atmta), 
            lambda message: message.photo and message.caption and message.caption.startswith('/at')
        )
        
        # 2. Для текстовых сообщений с командой /at (ответ на фото)
        dp.message.register(check_message_age(cmd_create_atmta), Command("at"))
        
        logger.info("Зарегистрирован обработчик для команды /at")
        
        # Регистрируем обработчик для команды /dem (Демотиватор)
        # 1. Для сообщений с фото и подписью /dem (Регистрируем в первую очередь, чтобы перехватывать до Command("dem"))
        dp.message.register(
            check_message_age(cmd_create_demotivator), 
            lambda message: message.photo and message.caption and message.caption.startswith('/dem')
        )
        
        # 2. Для текстовых сообщений с командой /dem (ответ на фото)
        dp.message.register(check_message_age(cmd_create_demotivator), Command("dem"))
        
        logger.info("Зарегистрирован обработчик для команды /dem")
        
        # Регистрируем обработчик для команды /jp (JPEG-артефакты)
        # 1. Для сообщений с фото и подписью /jp
        dp.message.register(
            check_message_age(cmd_jpeg_artifact), 
            lambda message: message.photo and message.caption and message.caption.startswith('/jp')
        )
        
        # 2. Для текстовых сообщений с командой /jp (ответ на фото)
        dp.message.register(check_message_age(cmd_jpeg_artifact), Command("jp"))
        
        logger.info("Зарегистрирован обработчик для команды /jp")
        

        
        # Регистрируем обработчик для команды /delmsg (удаление сообщений)
        dp.message.register(check_message_age(cmd_delete_message), Command("delmsg"))
        logger.info("Зарегистрирован обработчик для команды /delmsg")
        
        # Регистрируем обработчик для команды /help (справка по командам)
        dp.message.register(check_message_age(cmd_help), Command("help"))
        logger.info("Зарегистрирован обработчик для команды /help")
        
        # Регистрируем обработчик для команды /stats (статистика базы данных)
        dp.message.register(check_message_age(cmd_stats), Command("stats"))
        logger.info("Зарегистрирован обработчик для команды /stats")
        
        # Регистрируем обработчик для административной команды /exp (экспорт сообщений)
        dp.message.register(check_message_age(cmd_export_messages), Command("exp"))
        logger.info("Зарегистрирован обработчик для административной команды /exp")
        
        # Регистрируем обработчик для административной команды /adduser (добавление пользователей)
        dp.message.register(check_message_age(cmd_add_user), Command("adduser"))
        logger.info("Зарегистрирован обработчик для административной команды /adduser")
        
        # Регистрируем обработчик для административной команды /deluser (удаление пользователей)
        dp.message.register(check_message_age(cmd_delete_user), Command("deluser"))
        logger.info("Зарегистрирован обработчик для административной команды /deluser")
        
        # Регистрируем обработчик для административной команды /help2 (список админ-команд)
        dp.message.register(check_message_age(cmd_admin_help), Command("help2"))
        logger.info("Зарегистрирован обработчик для административной команды /help2")
        
        logger.info("Все разрешенные обработчики команд успешно зарегистрированы")
    except Exception as e:
        logger.error(f"Ошибка при регистрации обработчиков команд: {e}", exc_info=True)
