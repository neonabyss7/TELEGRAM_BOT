from aiogram import Dispatcher
from aiogram.types import Message, BufferedInputFile, ChatMemberUpdated
from datetime import datetime

from src.database.db_handler import save_filtered_message, save_sticker_to_db, save_animation_to_db, get_random_sticker_from_db, get_random_animation_from_db
from src.utils.message_filters import is_message_valid
from src.utils.text_generator import generate_sentence, generate_sentence_custom, generate_story
from src.utils.image_processor import create_meme, create_atmta_image, create_demotivator, create_jpeg_artifact
from src.utils.access_control import process_group_member, check_chat_access
from src.config import (
    DEFAULT_CHANCE,
    CHANCE_PREFER_SHORT_MESSAGE,
    TEXT_EVENT_STICKER_WEIGHT,
    TEXT_EVENT_GIF_WEIGHT,
    TEXT_EVENT_MESSAGE_WEIGHT,
    PHOTO_EVENT_MEME_WEIGHT,
    PHOTO_EVENT_ATMTA_WEIGHT,
    PHOTO_EVENT_DEMOTIVATOR_WEIGHT,
    PHOTO_EVENT_JPEG_ARTIFACT_WEIGHT,
    ALLOWED_GROUP_CHAT_ID,
    ADMIN_USER_ID
)

import logging
import random

logger = logging.getLogger(__name__)

# Глобальная переменная для хранения времени запуска бота
BOT_START_TIME = datetime.now().timestamp()

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

async def handle_message(message: Message):
    """
    Handle incoming text messages, filter them and save to database if valid
    
    Игнорирует старые сообщения, которые были получены когда бот был отключен
    """
    # Проверяем, не устарело ли сообщение (было отправлено до запуска бота)
    if is_message_outdated(message):
        return
    # Get user info
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    message_text = message.text
    
    # Log the incoming message
    logger.info(f"Received message from user {user_id}: {message_text}")
    
    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, user_id)
    if not has_access:
        logger.warning(f"Access denied for chat {chat_id}, user {user_id}")
        return
    
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    # Filter the message
    if is_message_valid(message_text):
        # Save valid message to database
        await save_filtered_message(
            user_id, 
            username, 
            first_name, 
            last_name, 
            message_text, 
            chat_id
        )
        logger.info(f"Message from user {user_id} passed filters and was saved")
        
        # Система случайных событий
        # Сначала определяем, сработает ли вообще какое-нибудь событие (шанс 3%)
        if random.random() < DEFAULT_CHANCE:  # Используем базовую константу из config.py
            # Веса для каждого типа события
            weights = [
                TEXT_EVENT_STICKER_WEIGHT,  # вес стикера
                TEXT_EVENT_GIF_WEIGHT,      # вес гифки
                TEXT_EVENT_MESSAGE_WEIGHT   # вес рандом сообщения
            ]
            
            # Выбираем тип события на основе весов
            event_type = random.choices(
                population=[0, 1, 2],  # 0 - стикер, 1 - гифка, 2 - рандом сообщение
                weights=weights,       # веса для каждого типа
                k=1                    # получаем 1 результат
            )[0]  # получаем первый (и единственный) элемент результата
            
            # Тип события: стикер
            if event_type == 0:
                logger.info("Случайное событие сработало. Выбран тип события: стикер")
                sticker_file_id = await get_random_sticker_from_db()
                if sticker_file_id:
                    await message.answer_sticker(sticker_file_id)
                    logger.info(f"Отправлен случайный стикер пользователю {user_id}")
                else:
                    logger.info("Сработал шанс случайного стикера, но стикеров в базе нет")
            
            # Тип события: гифка
            elif event_type == 1:
                logger.info("Случайное событие сработало. Выбран тип события: гифка")
                animation_file_id = await get_random_animation_from_db()
                if animation_file_id:
                    await message.answer_animation(animation_file_id)
                    logger.info(f"Отправлена случайная GIF-анимация пользователю {user_id}")
                else:
                    logger.info("Сработал шанс случайной GIF-анимации, но анимаций в базе нет")
            
            # Тип события: рандом сообщение
            elif event_type == 2:
                logger.info("Случайное событие сработало. Выбран тип события: рандом сообщение")
                
                # Определяем, что отправить: одно предложение или историю
                if random.random() < CHANCE_PREFER_SHORT_MESSAGE:  # 70% шанс на отправку одного предложения
                    logger.info("Будет отправлено одно предложение")
                    
                    # Генерируем предложение (аналогично команде /gm)
                    generated_text = generate_sentence()
                    
                    if generated_text:
                        await message.answer(generated_text)
                        logger.info(f"Отправлено случайное сгенерированное предложение пользователю {user_id}: {generated_text[:50]}...")
                    else:
                        logger.warning("Не удалось сгенерировать случайное предложение")
                else:  # Шанс на отправку истории (аналогично команде /story)
                    logger.info("Будет отправлена история")
                    
                    # Генерируем историю с случайным числом предложений от 2 до 5
                    sentences_count = random.randint(2, 5)
                    generated_story = generate_story(min_sentences=sentences_count, max_sentences=sentences_count)
                    
                    if generated_story:
                        await message.answer(generated_story)
                        logger.info(f"Отправлена случайная сгенерированная история из {sentences_count} предложений пользователю {user_id}")
                    else:
                        logger.warning("Не удалось сгенерировать случайную историю")
    else:
        logger.info(f"Message from user {user_id} filtered out (contains links, special characters, or mentions)")
        
async def handle_sticker(message: Message):
    """
    Handle incoming stickers, save them to database
    """
    # Проверяем, не устарело ли сообщение (было отправлено до запуска бота)
    if is_message_outdated(message):
        return
    # Get user info
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    
    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, user_id)
    if not has_access:
        logger.warning(f"Access denied for chat {chat_id}, user {user_id} (sticker)")
        return
    
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    # Получаем информацию о стикере
    sticker = message.sticker
    sticker_id = sticker.file_unique_id
    file_id = sticker.file_id
    set_name = sticker.set_name if sticker.set_name else "unknown_set"
    
    logger.info(f"Received sticker from user {user_id}, sticker_id: {sticker_id}")
    
    # Сохраняем стикер в базу
    saved = await save_sticker_to_db(sticker_id, file_id, set_name, user_id, chat_id)
    
    if saved:
        logger.info(f"Sticker {sticker_id} from user {user_id} saved to database")
    else:
        logger.info(f"Sticker {sticker_id} already exists in database")
        
async def handle_animation(message: Message):
    """
    Handle incoming GIF animations, save them to database
    """
    # Проверяем, не устарело ли сообщение (было отправлено до запуска бота)
    if is_message_outdated(message):
        return
    # Get user info
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    
    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, user_id)
    if not has_access:
        logger.warning(f"Access denied for chat {chat_id}, user {user_id} (animation)")
        return
    
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    # Получаем информацию о GIF-анимации
    animation = message.animation
    animation_id = animation.file_unique_id
    file_id = animation.file_id
    file_name = animation.file_name if animation.file_name else "unknown_file"
    mime_type = animation.mime_type if animation.mime_type else "unknown_mime"
    
    logger.info(f"Received animation from user {user_id}, animation_id: {animation_id}")
    
    # Сохраняем анимацию в базу
    saved = await save_animation_to_db(animation_id, file_id, file_name, mime_type, user_id, chat_id)
    
    if saved:
        logger.info(f"Animation {animation_id} from user {user_id} saved to database")
    else:
        logger.info(f"Animation {animation_id} already exists in database")

async def handle_photo(message: Message):
    """
    Handle incoming photos with a chance to create:
    1. A meme with random text (3% chance)
    2. An ATMTA (mirrored) image (3% chance)
    3. A demotivator (3% chance)
    4. JPEG artifacts (3% chance)
    """
    # Проверяем, не устарело ли сообщение (было отправлено до запуска бота)
    if is_message_outdated(message):
        return
    # Get user info
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    chat_id = message.chat.id
    
    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, user_id)
    if not has_access:
        logger.warning(f"Access denied for chat {chat_id}, user {user_id} (photo)")
        return
    
    # Если сообщение из разрешенной группы, добавляем пользователя в список разрешенных
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        await process_group_member(user_id, username, first_name, last_name)
    
    logger.info(f"Received photo from user {user_id}")
    
    try:
        # Получаем экземпляр бота и фото
        bot = message.bot
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        
        # Система случайных медиа-событий
        # Сначала определяем, сработает ли вообще какое-нибудь событие (шанс 3%)
        if random.random() < DEFAULT_CHANCE:  # Используем базовую константу из config.py
            # Веса для каждого типа медиа-события
            weights = [
                PHOTO_EVENT_MEME_WEIGHT,            # вес мема
                PHOTO_EVENT_ATMTA_WEIGHT,           # вес АТМТА
                PHOTO_EVENT_DEMOTIVATOR_WEIGHT,     # вес демотиватора
                PHOTO_EVENT_JPEG_ARTIFACT_WEIGHT,   # вес JPEG-артефактов
            ]
            
            # Выбираем тип события на основе весов
            media_event_type = random.choices(
                population=[0, 1, 2, 3],  # 0 - мем, 1 - АТМТА, 2 - демотиватор, 3 - JPEG-артефакты
                weights=weights,          # веса для каждого типа
                k=1                       # получаем 1 результат
            )[0]  # получаем первый (и единственный) элемент результата
            
            # Загружаем фото (делаем это один раз, независимо от типа события)
            downloaded_file = await bot.download_file(file_info.file_path)
            logger.info(f"Загружено изображение для обработки, file_id: {photo.file_id}")
            
            # Тип события: автоматический мем
            if media_event_type == 0:
                logger.info(f"Случайное медиа-событие сработало. Выбран тип: автомем")
                
                # Генерируем текст для мема
                meme_text = generate_sentence_custom(min_words=5, max_words=15)
                logger.info(f"Сгенерирован текст для автомема: {meme_text}")
                
                if not meme_text:
                    meme_text = "Когда забыл текст для мема"
                    logger.warning("Сгенерирован пустой текст для автомема, используется запасной вариант")
                
                # Создаем мем
                meme_bytes = await create_meme(downloaded_file.read(), meme_text)
                
                if meme_bytes:
                    # Отправляем мем (без подписи)
                    await message.answer_photo(
                        photo=BufferedInputFile(
                            meme_bytes, 
                            filename="automeme.jpg"
                        )
                    )
                    logger.info(f"Автомем успешно создан и отправлен пользователю {user_id}")
                else:
                    logger.warning("Не удалось создать автомем из изображения")
            
            # Тип события: АТМТА-эффект
            elif media_event_type == 1:
                logger.info(f"Случайное медиа-событие сработало. Выбран тип: АТМТА")
                
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
                    logger.info(f"АТМТА-изображение автоматически создано и отправлено пользователю {user_id}")
                else:
                    logger.warning("Не удалось создать АТМТА-изображение")
            
            # Тип события: демотиватор
            elif media_event_type == 2:
                logger.info(f"Случайное медиа-событие сработало. Выбран тип: демотиватор")
                
                # Генерируем текст для демотиватора
                demo_text = generate_sentence_custom(min_words=2, max_words=6)
                logger.info(f"Сгенерирован текст для демотиватора: {demo_text}")
                
                # Создаем демотиватор
                demotivator_bytes = await create_demotivator(downloaded_file.read(), demo_text)
                
                if demotivator_bytes:
                    # Отправляем демотиватор (без подписи)
                    await message.answer_photo(
                        photo=BufferedInputFile(
                            demotivator_bytes, 
                            filename="demotivator.jpg"
                        )
                    )
                    logger.info(f"Демотиватор автоматически создан и отправлен пользователю {user_id}")
                else:
                    logger.warning("Не удалось создать демотиватор из изображения")
            
            # Тип события: JPEG-артефакты
            elif media_event_type == 3:
                logger.info(f"Случайное медиа-событие сработало. Выбран тип: JPEG-артефакты")
                
                # Случайный уровень сжатия от 5 до 10 (чем выше, тем сильнее искажения)
                quality_level = random.randint(5, 10)
                logger.info(f"Выбран уровень качества для JPEG-артефактов: {quality_level}")
                
                # Создаем изображение с JPEG-артефактами
                jpeg_artifact_bytes = await create_jpeg_artifact(downloaded_file.read(), quality_level)
                
                if jpeg_artifact_bytes:
                    # Отправляем изображение с JPEG-артефактами (без подписи)
                    await message.answer_photo(
                        photo=BufferedInputFile(
                            jpeg_artifact_bytes, 
                            filename="jpeg_artifact.jpg"
                        )
                    )
                    logger.info(f"Изображение с JPEG-артефактами автоматически создано и отправлено пользователю {user_id}")
                else:
                    logger.warning("Не удалось создать изображение с JPEG-артефактами")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке автоматического создания мема/АТМТА/демотиватора/JPEG-артефактов: {e}", exc_info=True)

async def handle_chat_member_updated(event: ChatMemberUpdated):
    """
    Handle user joining or leaving the allowed group chat
    When a user joins the allowed group, add them to the database of allowed users
    """
    # Проверяем, что это событие из разрешенной группы
    chat_id = event.chat.id
    if chat_id != ALLOWED_GROUP_CHAT_ID:
        return
    
    # Получаем информацию о пользователе
    user = event.new_chat_member.user if event.new_chat_member else None
    if not user:
        logger.warning("No user information in chat member update event")
        return
    
    user_id = user.id
    username = user.username
    first_name = user.first_name
    last_name = user.last_name
    
    # Проверяем статус пользователя
    new_status = event.new_chat_member.status if event.new_chat_member else None
    old_status = event.old_chat_member.status if event.old_chat_member else None
    
    logger.info(f"ChatMemberUpdated event: User {user_id} ({username}) status changed from {old_status} to {new_status}")
    
    # Если пользователь вступил в группу или стал участником
    if new_status in ["member", "administrator", "creator"]:
        logger.info(f"User {user_id} ({username}) joined or is an active member of the allowed group")
        await process_group_member(user_id, username, first_name, last_name)
    # В будущем можно добавить обработку выхода пользователя из группы, если нужно

def register_message_handlers(dp: Dispatcher):
    """Register all message handlers"""
    # Регистрируем обработчик текстовых сообщений
    dp.message.register(handle_message, lambda message: message.text and not message.text.startswith('/'))
    
    # Регистрируем обработчик стикеров
    dp.message.register(handle_sticker, lambda message: message.sticker is not None)
    
    # Регистрируем обработчик GIF-анимаций
    dp.message.register(handle_animation, lambda message: message.animation is not None)
    
    # Регистрируем обработчик фотографий, но исключаем фото с подписью /mem, /at, /dem или /jp
    dp.message.register(
        handle_photo, 
        lambda message: message.photo is not None and 
                      len(message.photo) > 0 and 
                      (message.caption is None or 
                       (not message.caption.startswith('/mem') and 
                        not message.caption.startswith('/at') and
                        not message.caption.startswith('/dem') and
                        not message.caption.startswith('/jp')))
    )
    
    # Регистрируем обработчик для отслеживания изменений в группе
    dp.chat_member.register(handle_chat_member_updated)
    
    logger.info("Message handlers registered")