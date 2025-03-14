# Configuration file for Telegram bot

# Bot API token - используйте свой токен от @BotFather
# Приоритет: 1) переменная окружения TELEGRAM_BOT_TOKEN, 2) значение по умолчанию
import os
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "АПИ_ТОКЕН_ВАШЕГО_ТГ_БОТА")
# Для совместимости 
BOT_API_TOKEN = BOT_TOKEN

# Настройки часового пояса (московское время)
TIMEZONE_OFFSET = 3  # UTC+3

# Database settings
DATA_DIR = "data"
DATABASE_NAME = f"{DATA_DIR}/telegram_data.db"

# Allowed group chat ID - замените на ID вашей группы
# Можно установить через переменную окружения TELEGRAM_ALLOWED_GROUP
ALLOWED_GROUP_CHAT_ID = int(os.environ.get("TELEGRAM_ALLOWED_GROUP", "АЙДИ_ВАШЕГО_ГРУППОВОГО_ЧАТА"))

# Admin user ID - замените на ваш ID в Telegram
# Можно установить через переменную окружения TELEGRAM_ADMIN_ID
ADMIN_USER_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", "ВАШ_АЙДИ_В_ТГ"))

# ======== НАСТРОЙКИ ВЕРОЯТНОСТЕЙ СОБЫТИЙ ========
# Значение по умолчанию для вероятности случайного события
DEFAULT_CHANCE = 0.03  # 3%

# Настройки для текстовых сообщений (коэффициенты для расчета вероятностей)
TEXT_EVENT_STICKER_WEIGHT = 1.0
TEXT_EVENT_GIF_WEIGHT = 1.0
TEXT_EVENT_MESSAGE_WEIGHT = 1.0

# Настройки для фото (коэффициенты для расчета вероятностей)
PHOTO_EVENT_MEME_WEIGHT = 1.0
PHOTO_EVENT_ATMTA_WEIGHT = 1.0
PHOTO_EVENT_DEMOTIVATOR_WEIGHT = 1.0
PHOTO_EVENT_JPEG_ARTIFACT_WEIGHT = 1.0

# Настройки генерации текста
CHANCE_PREFER_SHORT_MESSAGE = 0.7  # 70% вероятность генерации короткого сообщения