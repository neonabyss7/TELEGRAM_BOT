import io
import logging
import random
import os
import tempfile
from PIL import Image, ImageDraw, ImageFont, ImageStat, ImageFilter, ImageEnhance, ImageOps
import textwrap
import base64
import math
from collections import Counter

logger = logging.getLogger(__name__)

# Настройки для создания мемов
DEFAULT_TEXT_COLOR = (255, 255, 255)  # белый
DEFAULT_OUTLINE_COLOR = (0, 0, 0)      # черный
DEFAULT_LINE_WIDTH = 20                # максимальное количество символов в строке
DEFAULT_PADDING = 20                   # отступ от края изображения
MIN_FONT_SIZE = 20                     # минимальный размер шрифта
MAX_FONT_SIZE = 80                     # максимальный размер шрифта
MIN_WORDS_PER_LINE = 3                 # минимальное количество слов в строке

# Пути к системным шрифтам (для разных ОС)
FONT_PATHS = [
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    # Windows
    "C:/Windows/Fonts/Arial.ttf",
    "C:/Windows/Fonts/ARIALBD.TTF",  # Arial Bold
    "C:/Windows/Fonts/CALIBRI.TTF",
    "C:/Windows/Fonts/CALIBRIB.TTF", # Calibri Bold
    # macOS
    "/Library/Fonts/Arial.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/SFNSDisplay-Bold.otf",
    "/System/Library/Fonts/SFNSDisplay-Regular.otf",
]

# Создаем временный файл со встроенным шрифтом
# Закодированный ttf-файл со шрифтом, который поддерживает кириллицу (DejaVuSans-Bold)
EMBEDDED_FONT_BASE64 = """
AAEAAAATAQAABAAwRkZUTXPB9PAAAAE8AAAAHEdERUaNwIfxAAABWAAAAjhHUE9T1BxgqAAAA5AA
AIg2R1NVQr1/LFYAAIvIAAAV2E9TLzJaV5iUAAChoAAAAFZjbWFwBLRH+QAAofgAABZeY3Z0ID65
MQgAALhYAAACVGZwZ21bAmvwAAC6rAAAAKxnYXNwAAcABwAAu1gAAAAMZ2x5ZpofOO4AALtkAAfv
AGhlYWQOJUeZAAiqZAAAADZoaGVhDq8fpAAIqpwAAAAkaG10eHw5EsMACKrAAABgzmtlcm6hAbx1
AAkLkAAAJB5sb2NhWB8AnAAJL7AAAGDUbWF4cB55Bi0ACZCEAAAAIG5hbWVyIpvoAAmQpAAAPTVw
b3N0vBtguQAJzdwAAO8NcHJlcHxhoucACrzsAAAHpwAAAAEAAAAAzD2izwAAAADTwikQAAAAANPC
KRAAAQAAAA4AAAIoAjAAAAACAFkAAwKwAAECsQLFAAMCxgLGAAECxwLKAAMCywLMAAECzQLRAAMC
0gLTAAEC1ALkAAMC5QLpAAEC6gL1AAMC9gL2AAEC9wL/AAMDAAMAAAEDAQMEAAMDBQMFAAEDBgMG
AAMDBwMHAAEDCAMIAAMDCQMKAAEDCwMMAAMDDQQXAAEEGAQcAAMEHQUNAAEFDgUOAAIFDwUQAAEF
EQUaAAMFGwUbAAEFHAUeAAMFHwUfAAEFIAUgAAMFIQUlAAEFJgUmAAMFJwVLAAEFTAVMAAMFTQVP
AAEFUAVUAAIFVQVzAAEFdAWAAAMFgQWQAAEFkQWRAAMFkgYTAAEGFAYcAAMGHQY/AAEGQAZAAAMG
QQZCAAEGQwZKAAMGSwZRAAEGUgZXAAMGWAj3AAEI+Aj9AAMI/gseAAELHwsfAAILIAspAAELKgss
AAILLQt/AAELgAuAAAILgQuRAAELkguYAAMLmQuZAAILmgudAAELngufAAILoAu3AAELuAu5AAIL
ugvSAAEL0wvTAAIL1BOsAAETrRO5AAITuhO6AAMTuxO7AAITvBPlAAET5hPmAAIT5xRjAAEUZBRk
AAMUZRRlAAEUZhRmAAMUZxRpAAIUahRqAAEUaxR1AAIUdhTqAAEU6xTyAAIU8xcNAAEXDhcXAAMX
GBc8AAEXPRc9AAMXPhdsAAEXbRd0AAMXdRfOAAEXzxfPAAMX0BgzAAEABAAAAAIAAAABAAAAAQAA
AAEAAAAKAdgCSgAUREZMVAB6YXJhYgCGYXJtbgCoYnJhaQC0Y2FucwDAY2hlcgDMY3lybADYZ2Vv
cgD0Z3JlawEAaGFuaQEQaGVicgEca2FuYQEqbGFvIA==
"""

# Глобальные переменные
DEFAULT_FONT = None
TEMP_FONT_FILE = None

# Переменная для отслеживания последнего использованного режима АТМТА
# 0: вертикальное зеркалирование левой половины
# 1: вертикальное зеркалирование правой половины
# 2: горизонтальное зеркалирование верхней половины
# 3: горизонтальное зеркалирование нижней половины
LAST_ATMTA_MODE = -1

def load_embedded_font(font_size=30):
    """
    Загружает встроенный шрифт из base64 строки с указанным размером
    
    Args:
        font_size (int): Размер шрифта
    
    Returns:
        PIL.ImageFont: Загруженный шрифт
    """
    global TEMP_FONT_FILE
    
    try:
        # Создаем временный файл для шрифта, если он еще не создан
        if TEMP_FONT_FILE is None or not os.path.exists(TEMP_FONT_FILE):
            fd, temp_path = tempfile.mkstemp(suffix='.ttf')
            
            # Записываем декодированные данные во временный файл
            with os.fdopen(fd, 'wb') as f:
                f.write(base64.b64decode(EMBEDDED_FONT_BASE64))
            
            # Сохраняем путь к временному файлу
            TEMP_FONT_FILE = temp_path
            logger.info(f"Создан временный файл шрифта: {temp_path}")
        
        # Загружаем шрифт с указанным размером
        font = ImageFont.truetype(TEMP_FONT_FILE, font_size)
        logger.info(f"Загружен встроенный шрифт с размером {font_size}px")
        return font
    except Exception as e:
        logger.error(f"Ошибка при загрузке встроенного шрифта: {e}", exc_info=True)
        return None

def load_font(font_size=30):
    """
    Загружает системный шрифт с поддержкой кириллицы с указанным размером
    
    Args:
        font_size (int): Размер шрифта
    
    Returns:
        PIL.ImageFont: Загруженный шрифт
    """
    # Сначала пробуем загрузить системные шрифты
    for font_path in FONT_PATHS:
        try:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
                logger.info(f"Загружен системный шрифт: {font_path} с размером {font_size}px")
                return font
        except Exception as e:
            logger.warning(f"Не удалось загрузить шрифт {font_path}: {e}")
    
    # Если системные шрифты не загрузились, используем встроенный
    embedded_font = load_embedded_font(font_size)
    if embedded_font:
        return embedded_font
    
    # Если все методы не сработали, используем встроенный PIL шрифт
    logger.warning("Используем стандартный шрифт PIL (кириллица может отображаться некорректно)")
    return ImageFont.load_default()

def get_dominant_colors(image, num_colors=5):
    """
    Определяет доминирующие цвета на изображении
    
    Args:
        image (PIL.Image): Исходное изображение
        num_colors (int): Количество доминирующих цветов для определения
        
    Returns:
        list: Список кортежей с доминирующими цветами в формате (R, G, B)
    """
    # Уменьшаем изображение для ускорения
    small_img = image.copy()
    small_img.thumbnail((100, 100))
    
    # Преобразуем в RGB, если необходимо
    if small_img.mode != 'RGB':
        small_img = small_img.convert('RGB')
    
    # Получаем все пиксели
    pixels = list(small_img.getdata())
    
    # Подсчитываем частоту цветов
    color_counter = Counter(pixels)
    
    # Получаем наиболее часто встречающиеся цвета
    dominant_colors = color_counter.most_common(num_colors)
    
    return [color[0] for color in dominant_colors]

def get_contrasting_colors(image):
    """
    Определяет оптимальные контрастные цвета для текста и обводки
    на основе анализа изображения
    
    Args:
        image (PIL.Image): Исходное изображение
        
    Returns:
        tuple: (text_color, outline_color) - цвета для текста и обводки
    """
    try:
        # Получаем доминирующие цвета
        dominant_colors = get_dominant_colors(image)
        
        # Если не удалось определить цвета, используем стандартные
        if not dominant_colors:
            return DEFAULT_TEXT_COLOR, DEFAULT_OUTLINE_COLOR
        
        # Определяем среднюю яркость изображения
        # Используем ImageStat для получения средней яркости
        stat = ImageStat.Stat(image)
        brightness = sum(stat.mean) / 3
        
        # Вычисляем яркость доминирующего цвета
        main_color = dominant_colors[0]
        main_brightness = sum(main_color) / 3
        
        # Выбираем основной цвет текста
        if brightness < 128:
            # На темном фоне - светлый текст
            text_color = (255, 255, 255)  # Белый
        else:
            # На светлом фоне - темный текст
            text_color = (0, 0, 0)  # Черный
        
        # Выбираем цвет обводки, наиболее контрастный с текстом и фоном
        if text_color == (255, 255, 255):
            # Для белого текста - темная обводка, но не черная, если фон не черный
            if main_brightness < 30:  # Очень темный фон
                outline_color = (100, 100, 100)  # Серый
            else:
                outline_color = (0, 0, 0)  # Черный
        else:
            # Для черного текста - светлая обводка, но не белая, если фон не белый
            if main_brightness > 220:  # Очень светлый фон
                outline_color = (100, 100, 100)  # Серый
            else:
                outline_color = (255, 255, 255)  # Белый
        
        return text_color, outline_color
        
    except Exception as e:
        logger.warning(f"Ошибка при определении контрастных цветов: {e}")
        return DEFAULT_TEXT_COLOR, DEFAULT_OUTLINE_COLOR

def optimize_text_for_meme(text, width):
    """
    Оптимизирует текст для мема, чтобы избежать "лесенки" из коротких строк
    
    Args:
        text (str): Исходный текст
        width (int): Максимальное количество символов в строке
        
    Returns:
        str: Оптимизированный текст с переносами строк
    """
    # Разбиваем текст на слова
    words = text.split()
    
    # Если текст слишком короткий, просто возвращаем его без изменений
    if len(words) <= MIN_WORDS_PER_LINE:
        return text
    
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        # Если текущая строка пуста, добавляем слово в любом случае
        if not current_line:
            current_line.append(word)
            current_length = len(word)
        # Если добавление слова не превысит ограничение ширины
        elif current_length + len(word) + 1 <= width:
            current_line.append(word)
            current_length += len(word) + 1  # +1 для пробела
        # Текущая строка полна, начинаем новую
        else:
            # Проверяем, не слишком ли короткая получилась строка
            if len(current_line) < MIN_WORDS_PER_LINE and len(words) > MIN_WORDS_PER_LINE:
                # Забираем слово из следующей строки, если это не последняя строка
                if len(words) > MIN_WORDS_PER_LINE:
                    current_line.append(word)
                    lines.append(' '.join(current_line))
                    current_line = []
                    current_length = 0
                    continue
            
            lines.append(' '.join(current_line))
            current_line = [word]
            current_length = len(word)
    
    # Добавляем последнюю строку, если она есть
    if current_line:
        lines.append(' '.join(current_line))
    
    return '\n'.join(lines)

def wrap_text(text, width, max_lines=6):
    """
    Разбивает текст на строки заданной ширины с оптимизацией для мемов
    
    Args:
        text (str): Исходный текст
        width (int): Максимальное количество символов в строке
        max_lines (int): Максимальное количество строк
        
    Returns:
        str: Текст, разбитый на строки с переносами
    """
    # Уменьшаем ширину строки для длинного текста
    if len(text) > 50:
        width = width - 5
    
    # Сначала получаем оптимизированный текст
    wrapped_text = optimize_text_for_meme(text, width)
    
    # Проверяем, не слишком ли много строк получилось
    lines = wrapped_text.split('\n')
    if len(lines) > max_lines:
        # Объединяем строки, увеличивая ширину, пока количество строк не станет допустимым
        while len(lines) > max_lines and width < 40:
            width += 2
            wrapped_text = optimize_text_for_meme(text, width)
            lines = wrapped_text.split('\n')
        
        # Если количество строк все еще превышает максимум, просто обрезаем текст
        if len(lines) > max_lines:
            # Оставляем только max_lines строк и добавляем "..."
            lines = lines[:max_lines-1] + [lines[max_lines-1] + "..."]
            wrapped_text = '\n'.join(lines)
    
    return wrapped_text

def add_text_manually(img, text, position):
    """
    Альтернативный метод добавления текста на изображение для случаев,
    когда стандартный метод не работает
    
    Args:
        img (PIL.Image): Исходное изображение
        text (str): Текст для добавления
        position (str): Позиция текста: "top", "bottom" или "center"
    
    Returns:
        PIL.Image: Изображение с добавленным текстом
    """
    draw = ImageDraw.Draw(img)
    img_width, img_height = img.size
    
    # Разбиваем текст на строки
    lines = text.split('\n')
    line_height = 30  # Высота строки
    text_height = len(lines) * line_height
    
    # Определяем y-координату для начала текста
    if position == "top":
        y_pos = DEFAULT_PADDING
    elif position == "center":
        y_pos = (img_height - text_height) // 2
    else:  # "bottom"
        y_pos = img_height - text_height - DEFAULT_PADDING
    
    # Рисуем каждую строку текста
    for i, line in enumerate(lines):
        # Примерно центрируем строку
        text_width = len(line) * 15  # Приблизительная ширина
        x_pos = (img_width - text_width) // 2
        
        # Позиция для этой строки
        line_y = y_pos + i * line_height
        
        # Рисуем обводку
        for dx, dy in [(x, y) for x in range(-2, 3) for y in range(-2, 3) if (x != 0 or y != 0)]:
            draw.text((x_pos + dx, line_y + dy), line, fill=DEFAULT_OUTLINE_COLOR)
        
        # Рисуем текст
        draw.text((x_pos, line_y), line, fill=DEFAULT_TEXT_COLOR)
    
    return img

def add_text_to_image(image, text, position="bottom"):
    """
    Добавляет текст на изображение в стиле мема с адаптивным размером шрифта
    и автоматическим выбором контрастных цветов
    
    Args:
        image (PIL.Image): Исходное изображение
        text (str): Текст для добавления
        position (str): Позиция текста: "top", "bottom" или "center"
        
    Returns:
        PIL.Image: Изображение с добавленным текстом
    """
    # Создаем копию изображения для редактирования
    img = image.copy()
    img_width, img_height = img.size
    
    # Определяем оптимальные цвета для текста и обводки на основе анализа изображения
    text_color, outline_color = get_contrasting_colors(img)
    logger.info(f"Автоматически выбраны цвета для текста: {text_color} и обводки: {outline_color}")
    
    # Определяем размер шрифта на основе размера изображения
    # Рассчитываем оптимальный размер шрифта (примерно 5% от высоты изображения)
    adaptive_font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, int(img_height * 0.05)))
    logger.info(f"Адаптивный размер шрифта: {adaptive_font_size} пикселей для изображения {img_width}x{img_height}")
    
    # Загружаем шрифт с адаптивным размером
    font = load_font(adaptive_font_size)
    
    draw = ImageDraw.Draw(img)
    
    # Подготавливаем текст (разбиваем на строки)
    # Для маленьких изображений делаем более короткие строки
    if img_width < 500:
        line_width = 10
    else:
        line_width = DEFAULT_LINE_WIDTH
    
    # Определяем максимальное количество строк на основе размера изображения
    max_lines = max(2, min(8, int(img_height / (adaptive_font_size * 1.5))))
    
    # Адаптируем текст к размеру изображения
    wrapped_text = wrap_text(text, line_width, max_lines=max_lines)
    
    try:
        # Пробуем стандартный метод с multiline_text
        # Рассчитываем размеры текста
        try:
            text_width, text_height = draw.multiline_textbbox((0, 0), wrapped_text, font=font)[2:4]
        except Exception as e:
            logger.warning(f"Ошибка при определении размеров текста: {e}")
            text_width = len(wrapped_text) * (adaptive_font_size // 2)
            text_height = wrapped_text.count('\n') * (adaptive_font_size + 10) + adaptive_font_size
        
        # Определяем координаты для размещения текста
        if position == "top":
            text_position = ((img.width - text_width) // 2, DEFAULT_PADDING)
        elif position == "center":
            text_position = ((img.width - text_width) // 2, (img.height - text_height) // 2)
        else:  # "bottom" по умолчанию
            bottom_y = max(0, img.height - text_height - DEFAULT_PADDING)
            text_position = ((img.width - text_width) // 2, bottom_y)
        
        # Толщина обводки зависит от размера шрифта
        outline_size = max(1, min(3, adaptive_font_size // 10))
        offsets = [(ox, oy) for ox in range(-outline_size, outline_size+1) 
                  for oy in range(-outline_size, outline_size+1) 
                  if (ox, oy) != (0, 0)]
        
        # Создаем эффект обводки для улучшения читаемости текста
        for offset_x, offset_y in offsets:
            draw.multiline_text(
                (text_position[0] + offset_x, text_position[1] + offset_y),
                wrapped_text,
                fill=outline_color,  # Используем вычисленный цвет обводки
                font=font,
                align="center",
            )
        
        # Добавляем основной текст
        draw.multiline_text(
            text_position,
            wrapped_text,
            fill=text_color,  # Используем вычисленный цвет текста
            font=font,
            align="center",
        )
        
        return img
    except Exception as e:
        # Если основной метод не сработал, используем запасной
        logger.warning(f"Ошибка при стандартном добавлении текста: {e}, пробуем альтернативный метод")
        
        # Модифицируем запасной метод, чтобы он тоже использовал адаптивный размер
        draw = ImageDraw.Draw(img)
        lines = wrapped_text.split('\n')
        line_height = adaptive_font_size + 10  # Высота строки с отступом
        text_height = len(lines) * line_height
        
        # Определяем y-координату для начала текста
        if position == "top":
            y_pos = DEFAULT_PADDING
        elif position == "center":
            y_pos = (img_height - text_height) // 2
        else:  # "bottom"
            y_pos = img_height - text_height - DEFAULT_PADDING
        
        # Рисуем каждую строку текста
        for i, line in enumerate(lines):
            # Примерно центрируем строку
            text_width = len(line) * (adaptive_font_size // 2)
            x_pos = (img_width - text_width) // 2
            
            # Позиция для этой строки
            line_y = y_pos + i * line_height
            
            # Рисуем обводку
            outline_size = max(1, min(3, adaptive_font_size // 10))
            for dx, dy in [(x, y) for x in range(-outline_size, outline_size+1) 
                         for y in range(-outline_size, outline_size+1) 
                         if (x != 0 or y != 0)]:
                draw.text((x_pos + dx, line_y + dy), line, fill=outline_color, font=font)  # Используем вычисленный цвет обводки
            
            # Рисуем текст
            draw.text((x_pos, line_y), line, fill=text_color, font=font)  # Используем вычисленный цвет текста
        
        return img

async def create_atmta_image(image_bytes):
    """
    Создает зеркальный эффект АТМТА (или САС) из изображения
    с чередованием режимов зеркалирования
    
    Args:
        image_bytes (bytes или BytesIO): Байты изображения или объект BytesIO
        
    Returns:
        bytes: Байты изображения с эффектом АТМТА
    """
    global LAST_ATMTA_MODE
    
    try:
        # Импортируем PIL модули локально для предотвращения проблем с областью видимости при запуске на локальной машине
        from PIL import Image, ImageOps
        
        # Загружаем изображение из байтов
        if isinstance(image_bytes, io.BytesIO):
            image = Image.open(image_bytes)
        else:
            image_stream = io.BytesIO(image_bytes)
            image = Image.open(image_stream)
        
        # Преобразуем в RGB, если необходимо
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        width, height = image.size
        
        # Определяем, будем делить изображение вертикально или горизонтально
        # Вертикально (лево/право) если ширина >= высоты, иначе горизонтально (верх/низ)
        is_vertical_split = width >= height
        
        # Выбираем режим зеркалирования, чередуя их последовательно без учета пропорций изображения
        # Режимы:
        # 0: вертикальное зеркалирование левой половины
        # 1: вертикальное зеркалирование правой половины
        # 2: горизонтальное зеркалирование верхней половины
        # 3: горизонтальное зеркалирование нижней половины
        
        # Увеличиваем счетчик режимов
        LAST_ATMTA_MODE = (LAST_ATMTA_MODE + 1) % 4
        
        # Определяем тип зеркалирования на основе режима
        if LAST_ATMTA_MODE < 2:
            # Вертикальное зеркалирование
            use_vertical_split = True
            use_first_half = (LAST_ATMTA_MODE == 0)  # 0 - левая половина, 1 - правая половина
            logger.info(f"Используем режим АТМТА #{LAST_ATMTA_MODE}: вертикальное зеркалирование {'левой' if use_first_half else 'правой'} половины")
        else:
            # Горизонтальное зеркалирование
            use_vertical_split = False
            use_first_half = (LAST_ATMTA_MODE == 2)  # 2 - верхняя половина, 3 - нижняя половина
            logger.info(f"Используем режим АТМТА #{LAST_ATMTA_MODE}: горизонтальное зеркалирование {'верхней' if use_first_half else 'нижней'} половины")
        
        # Сохраняем оригинальные размеры изображения
        original_width, original_height = image.size
        logger.info(f"Оригинальный размер изображения для ATMTA: {original_width}x{original_height}")
        
        # Создаем новое изображение
        if use_vertical_split:
            # Вертикальное разделение
            half_width = width // 2
            
            # Выбираем нужную половину
            if use_first_half:
                # Левая половина
                half = image.crop((0, 0, half_width, height))
                # Зеркально отражаем её
                mirrored = half.transpose(Image.FLIP_LEFT_RIGHT)
                # Создаем новое изображение с зеркальной левой половиной
                result = Image.new('RGB', (width, height))
                result.paste(half, (0, 0))
                result.paste(mirrored, (half_width, 0))
            else:
                # Правая половина
                half = image.crop((half_width, 0, width, height))
                # Зеркально отражаем её
                mirrored = half.transpose(Image.FLIP_LEFT_RIGHT)
                # Создаем новое изображение с зеркальной правой половиной
                result = Image.new('RGB', (width, height))
                result.paste(mirrored, (0, 0))
                result.paste(half, (half_width, 0))
        else:
            # Горизонтальное разделение
            half_height = height // 2
            
            # Выбираем нужную половину
            if use_first_half:
                # Верхняя половина
                half = image.crop((0, 0, width, half_height))
                # Зеркально отражаем её
                mirrored = half.transpose(Image.FLIP_TOP_BOTTOM)
                # Создаем новое изображение с зеркальной верхней половиной
                result = Image.new('RGB', (width, height))
                result.paste(half, (0, 0))
                result.paste(mirrored, (0, half_height))
            else:
                # Нижняя половина
                half = image.crop((0, half_height, width, height))
                # Зеркально отражаем её
                mirrored = half.transpose(Image.FLIP_TOP_BOTTOM)
                # Создаем новое изображение с зеркальной нижней половиной
                result = Image.new('RGB', (width, height))
                result.paste(mirrored, (0, 0))
                result.paste(half, (0, half_height))
        
        # Восстанавливаем исходный размер изображения (если он был изменен в процессе)
        if result.size != (original_width, original_height):
            logger.info(f"Восстанавливаем исходный размер для ATMTA: {original_width}x{original_height}")
            try:
                # Используем константы для Pillow >= 9.0
                from PIL.Image import Resampling
                result = result.resize((original_width, original_height), resample=Resampling.LANCZOS)
            except (ImportError, AttributeError):
                try:
                    # Для старых версий PIL, используем константы Pillow
                    result = result.resize((original_width, original_height), resample=Image.LANCZOS)
                except (ImportError, AttributeError):
                    # Fallback для очень старых версий
                    result = result.resize((original_width, original_height), resample=Image.BICUBIC)
        
        # Добавляем текст "АТМТА" или "САС"
        text = random.choice(["АТМТА", "САС"])
        position = random.choice(["top", "bottom", "center"])
        
        # Добавляем текст с использованием существующей функции
        result_with_text = add_text_to_image(result, text, position)
        
        # Сохраняем результат в байты
        output_stream = io.BytesIO()
        result_with_text.save(output_stream, format=image.format or "JPEG", quality=90)
        output_stream.seek(0)
        
        logger.info(f"АТМТА-изображение успешно создано с текстом {text} в позиции {position}")
        return output_stream.getvalue()
        
    except Exception as e:
        logger.error(f"Ошибка при создании АТМТА-изображения: {e}", exc_info=True)
        return None

async def create_demotivator(image_bytes, text=None):
    """
    Создает демотиватор из изображения и текста
    
    Args:
        image_bytes (bytes или BytesIO): Байты изображения или объект BytesIO
        text (str, optional): Текст для демотиватора. Если None, будет сгенерирован случайный текст.
        
    Returns:
        bytes: Байты изображения-демотиватора
    """
    try:
        # Импортируем PIL модули локально для предотвращения проблем с областью видимости при запуске на локальной машине
        from PIL import Image, ImageDraw
        
        # Загружаем изображение из байтов
        if isinstance(image_bytes, io.BytesIO):
            image = Image.open(image_bytes)
        else:
            image_stream = io.BytesIO(image_bytes)
            image = Image.open(image_stream)
        
        # Если текст не передан, используем случайную фразу
        if text is None:
            from src.utils.text_generator import generate_sentence
            text = generate_sentence(min_words=2, max_words=6)
        
        # Получаем размеры исходного изображения и сохраняем их для будущего использования
        width, height = image.size
        original_width, original_height = width, height
        logger.info(f"Оригинальный размер изображения для демотиватора: {original_width}x{original_height}")
        
        # Создаем черный фон для демотиватора с отступами
        border = 3  # Белая рамка
        margin = 50  # Отступ от рамки до края
        new_width = width + 2 * (border + margin)
        new_height = height + 2 * (border + margin) + 100  # Дополнительно для текста
        
        # Создаем черный фон
        demotivator = Image.new('RGB', (new_width, new_height), color=(0, 0, 0))
        
        # Создаем белую рамку
        white_frame = Image.new('RGB', (width + 2 * border, height + 2 * border), color=(255, 255, 255))
        
        # Размещаем изображение в центре белой рамки
        white_frame.paste(image, (border, border))
        
        # Размещаем белую рамку с изображением на черном фоне
        demotivator.paste(white_frame, (margin, margin))
        
        # Загружаем шрифт для текста
        font_size = min(30, width // 20)  # Адаптивный размер шрифта
        font = load_font(font_size)
        
        # Проверяем и ограничиваем длину текста
        max_chars_per_line = new_width // (font_size // 2)
        max_lines = 3  # Максимальное количество строк для демотиватора
        
        # Преобразуем текст в подходящий формат, если он слишком длинный
        if len(text) > max_chars_per_line:
            # Разбиваем текст на строки
            words = text.split()
            lines = []
            current_line = []
            current_length = 0
            
            for word in words:
                # Если добавление слова не превысит ограничение или строка пуста
                if current_length + len(word) + 1 <= max_chars_per_line or not current_line:
                    current_line.append(word)
                    current_length += len(word) + 1  # +1 для пробела
                else:
                    # Строка заполнена, начинаем новую
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = len(word)
            
            # Добавляем последнюю строку
            if current_line:
                lines.append(' '.join(current_line))
            
            # Ограничиваем количество строк
            if len(lines) > max_lines:
                lines = lines[:max_lines-1] + [lines[max_lines-1] + "..."]
            
            text = '\n'.join(lines)
            logger.info(f"Текст демотиватора адаптирован: {text}")
        
        # Рисуем текст под изображением
        draw = ImageDraw.Draw(demotivator)
        
        # Определяем размер текста и его позицию
        try:
            # Для новых версий PIL/Pillow (оптимальный метод)
            text_width, text_height = draw.multiline_textbbox((0, 0), text, font=font)[2:4]
        except AttributeError:
            try:
                # Альтернативный метод для новых версий
                text_width, text_height = font.getbbox(text)[2:]
            except AttributeError:
                # Для случая, когда оба метода не поддерживаются, оцениваем размер примерно
                text_width = len(text) * (font_size // 2)
                text_height = font_size * (1 + text.count('\n'))
        
        # Проверяем, не выходит ли текст за границы изображения
        if text_width > new_width - 2 * margin:
            # Уменьшаем шрифт, если текст слишком широкий
            scaling_factor = (new_width - 2 * margin) / text_width
            new_font_size = max(MIN_FONT_SIZE, int(font_size * scaling_factor * 0.9))  # Немного уменьшаем для гарантии
            font = load_font(new_font_size)
            logger.info(f"Шрифт уменьшен до {new_font_size}px для соответствия ширине")
            
            # Пересчитываем размеры текста
            try:
                text_width, text_height = draw.multiline_textbbox((0, 0), text, font=font)[2:4]
            except Exception:
                text_width = len(text.replace('\n', '')) * (new_font_size // 2)
                text_height = text.count('\n') * (new_font_size + 5) + new_font_size
        
        # Рассчитываем позицию текста (центрировано по горизонтали)
        text_position = ((new_width - text_width) // 2, height + 2 * (border + margin) + 20)
        
        # Рисуем текст
        draw.multiline_text(text_position, text, font=font, fill=(255, 255, 255), align="center")
        
        # Для демотиватора мы сохраняем размер рамки и не восстанавливаем 
        # исходный размер, так как это часть стиля демотиватора

        # Сохраняем результат в байты с высоким качеством
        output_stream = io.BytesIO()
        demotivator.save(output_stream, format="JPEG", quality=92)
        output_stream.seek(0)
        
        logger.info(f"Демотиватор успешно создан с текстом: {text}")
        return output_stream.getvalue()
        
    except Exception as e:
        logger.error(f"Ошибка при создании демотиватора: {e}", exc_info=True)
        return None



async def create_jpeg_artifact(image_bytes, quality_level=5):
    """
    Намеренно ухудшает качество изображения, добавляя JPEG-артефакты,
    искажения, шумы и другие эффекты "глубокой жарки"
    
    Args:
        image_bytes (bytes или BytesIO): Байты изображения или объект BytesIO
        quality_level (int): Уровень "порчи" от 1 до 10 (10 - максимальная порча)
        
    Returns:
        bytes: Байты испорченного изображения
    """
    try:
        # Для устранения проблемы с областью видимости при запуске локально
        from PIL import Image, ImageEnhance, ImageFilter
        
        # Преобразуем входные данные в BytesIO, если нужно
        if isinstance(image_bytes, bytes):
            image_data = io.BytesIO(image_bytes)
        else:
            image_data = image_bytes
        
        # Открываем изображение с помощью PIL
        img = Image.open(image_data)
        
        # Приводим к RGB, если нужно (для поддержки PNG с прозрачностью)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Расширенный набор эффектов для более сильной и разнообразной порчи изображения
        
        # Автоматически выбираем режимы порчи изображения (можно применить несколько)
        effects_to_apply = []
        
        # Гарантированно применяем базовые эффекты
        effects_to_apply.append("scaling")  # Масштабирование
        effects_to_apply.append("color_enhancement")  # Усиление цвета, контраста и яркости
        effects_to_apply.append("noise")  # Добавление шума
        effects_to_apply.append("jpeg_compression")  # JPEG-компрессия
        
        # Дополнительные эффекты применяем с некоторой вероятностью
        if random.random() < 0.7:
            effects_to_apply.append("channel_shift")  # Смещение цветовых каналов
        
        if random.random() < 0.6:
            effects_to_apply.append("pixelate")  # Пикселизация частей изображения
        
        if random.random() < 0.5:
            effects_to_apply.append("glitch_blocks")  # Глитч-блоки
        
        if random.random() < 0.4:
            effects_to_apply.append("invert_areas")  # Инверсия цветов в отдельных областях
        
        # Определяем общий уровень порчи - усиливаем качество базового quality_level
        actual_quality_level = min(10, quality_level + random.randint(0, 3))
        logger.info(f"Фактический уровень порчи: {actual_quality_level}, выбранные эффекты: {effects_to_apply}")
        
        # Применяем выбранные эффекты
        
        # Сохраняем исходный размер изображения для восстановления в конце
        original_width, original_height = img.size
        
        # 1. Масштабирование (если выбрано) - для создания эффектов, но с сохранением исходного размера
        if "scaling" in effects_to_apply:
            # Выбираем режим масштабирования случайно для большего разнообразия
            # Используем корректные константы для разных версий Pillow
            try:
                # Получаем константы для Pillow >= 9.0
                from PIL import Image
                from PIL.Image import Resampling
                downscale_mode = random.choice([Resampling.NEAREST, Resampling.BILINEAR, Resampling.BICUBIC])
                upscale_mode = random.choice([Resampling.NEAREST, Resampling.BILINEAR])
            except (ImportError, AttributeError):
                # Используем константы для Pillow < 9.0 (целочисленные константы)
                # В старых версиях Pillow используются просто целочисленные константы
                downscale_mode = random.choice([Image.NEAREST, Image.BILINEAR, Image.BICUBIC])
                upscale_mode = random.choice([Image.NEAREST, Image.BILINEAR])
            
            # Более агрессивное масштабирование для более высоких уровней порчи
            # Но оставляем размер изображения не менее 20% от исходного
            scale_factor = max(0.2, 0.5 - (actual_quality_level * 0.03))
            small_size = (int(img.width * scale_factor), int(img.height * scale_factor))
            
            # Временно уменьшаем для создания артефактов
            img = img.resize(small_size, resample=downscale_mode)
            
            # Увеличиваем до произвольного размера, чтобы создать эффекты
            # (но потом восстановим исходный размер)
            upscale_factor = random.uniform(1.2, 1.5)
            img = img.resize((int(img.width * upscale_factor), int(img.height * upscale_factor)), resample=upscale_mode)
        
        # 2. Улучшение цвета, контраста и яркости (если выбрано)
        if "color_enhancement" in effects_to_apply:
            from PIL import ImageEnhance
            
            # Контраст
            enhancer = ImageEnhance.Contrast(img)
            contrast_factor = random.uniform(1.7, 2.8)
            img = enhancer.enhance(contrast_factor)
            
            # Яркость
            enhancer = ImageEnhance.Brightness(img)
            brightness_factor = random.uniform(0.6, 1.4)
            img = enhancer.enhance(brightness_factor)
            
            # Цветность
            enhancer = ImageEnhance.Color(img)
            color_factor = random.uniform(1.8, 2.5)
            img = enhancer.enhance(color_factor)
            
            # Резкость
            enhancer = ImageEnhance.Sharpness(img)
            sharpness_factor = random.uniform(2.0, 5.0)
            img = enhancer.enhance(sharpness_factor)
        
        # 3. Смещение цветовых каналов (если выбрано)
        if "channel_shift" in effects_to_apply:
            # Разделяем изображение на отдельные каналы
            r, g, b = img.split()
            
            # Смещаем каналы на несколько пикселей в разных направлениях
            shift_range = max(3, min(15, actual_quality_level * 2))
            r_shift = (random.randint(-shift_range, shift_range), random.randint(-shift_range, shift_range))
            g_shift = (random.randint(-shift_range, shift_range), random.randint(-shift_range, shift_range))
            b_shift = (random.randint(-shift_range, shift_range), random.randint(-shift_range, shift_range))
            
            # Создаем новое изображение со смещенными каналами
            shifted_r = Image.new('L', img.size)
            shifted_g = Image.new('L', img.size)
            shifted_b = Image.new('L', img.size)
            
            shifted_r.paste(r, r_shift)
            shifted_g.paste(g, g_shift)
            shifted_b.paste(b, b_shift)
            
            img = Image.merge('RGB', (shifted_r, shifted_g, shifted_b))
        
        # 4. Пикселизация частей изображения (если выбрано)
        if "pixelate" in effects_to_apply:
            # Создаем несколько случайных квадратных областей пикселизации
            num_areas = random.randint(3, 8)
            
            for _ in range(num_areas):
                # Определяем размер и положение области пикселизации
                area_size = random.randint(20, max(30, img.width // 4))
                x = random.randint(0, img.width - area_size)
                y = random.randint(0, img.height - area_size)
                
                # Вырезаем область
                area = img.crop((x, y, x + area_size, y + area_size))
                
                # Пикселизируем область (уменьшаем и увеличиваем обратно)
                pixelate_factor = random.randint(4, 10)  # Степень пикселизации
                # Используем корректные константы для разных версий Pillow
                try:
                    # Используем константы Resampling для Pillow >= 9.0
                    from PIL.Image import Resampling
                    pixelated = area.resize(
                        (area_size // pixelate_factor, area_size // pixelate_factor),
                        resample=Resampling.NEAREST
                    ).resize((area_size, area_size), resample=Resampling.NEAREST)
                except (ImportError, AttributeError):
                    # Fallback для старых версий Pillow
                    pixelated = area.resize(
                        (area_size // pixelate_factor, area_size // pixelate_factor),
                        resample=Image.NEAREST
                    ).resize((area_size, area_size), resample=Image.NEAREST)
                
                # Вставляем обратно пикселизированную область
                img.paste(pixelated, (x, y))
        
        # 5. Добавляем глитч-блоки (если выбрано)
        if "glitch_blocks" in effects_to_apply:
            # Создаем несколько горизонтальных глитч-блоков
            num_blocks = random.randint(2, 5)
            height = img.height
            
            for _ in range(num_blocks):
                # Выбираем случайную строку для глитча
                y_start = random.randint(0, height - 10)
                block_height = random.randint(5, 20)
                y_end = min(y_start + block_height, height)
                
                # Вырезаем полосу изображения
                strip = img.crop((0, y_start, img.width, y_end))
                
                # Смещаем полосу по горизонтали
                shift_amount = random.randint(-img.width // 3, img.width // 3)
                
                # Разбиваем полосу на части и смещаем каждую
                num_segments = random.randint(2, 5)
                segment_width = img.width // num_segments
                
                for i in range(num_segments):
                    segment = strip.crop((i * segment_width, 0, (i + 1) * segment_width, block_height))
                    
                    # Случайное смещение для каждого сегмента
                    segment_shift = random.randint(-img.width // 4, img.width // 4)
                    
                    # Вычисляем позицию вставки с учетом горизонтального заворачивания
                    paste_x = (i * segment_width + segment_shift) % img.width
                    
                    # Вставляем сегмент обратно в основное изображение
                    img.paste(segment, (paste_x, y_start))
        
        # 6. Инверсия цветов в отдельных областях (если выбрано)
        if "invert_areas" in effects_to_apply:
            # Выбираем случайное количество областей для инверсии
            num_invert_areas = random.randint(1, 3)
            
            for _ in range(num_invert_areas):
                # Определяем размер и положение области инверсии
                area_size = random.randint(30, max(50, img.width // 3))
                x = random.randint(0, img.width - area_size)
                y = random.randint(0, img.height - area_size)
                
                # Вырезаем область
                area = img.crop((x, y, x + area_size, y + area_size))
                
                # Инвертируем цвета в этой области
                from PIL import ImageOps
                inverted_area = ImageOps.invert(area)
                
                # Вставляем инвертированную область обратно
                img.paste(inverted_area, (x, y))
        
        # 7. Добавляем шум (имитация артефактов JPEG) (если выбрано)
        if "noise" in effects_to_apply:
            pixels = img.load()
            # Увеличиваем интенсивность шума в зависимости от уровня порчи
            noise_intensity = random.randint(10, 10 + actual_quality_level * 5)
            # Увеличиваем процент затронутых пикселей в зависимости от уровня порчи
            noise_coverage = min(0.2, 0.05 + (actual_quality_level * 0.015))
            
            for y in range(img.height):
                for x in range(img.width):
                    if random.random() < noise_coverage:
                        r, g, b = pixels[x, y]
                        
                        # Выбираем между обычным шумом и "сбитыми" пикселями (полностью случайными значениями)
                        if random.random() < 0.2:
                            # Полностью случайные значения (сбитые пиксели)
                            noise_r = random.randint(0, 255)
                            noise_g = random.randint(0, 255)
                            noise_b = random.randint(0, 255)
                        else:
                            # Обычный шум - добавляем случайное значение к существующему
                            noise_r = max(0, min(255, r + random.randint(-noise_intensity, noise_intensity)))
                            noise_g = max(0, min(255, g + random.randint(-noise_intensity, noise_intensity)))
                            noise_b = max(0, min(255, b + random.randint(-noise_intensity, noise_intensity)))
                        
                        pixels[x, y] = (noise_r, noise_g, noise_b)
        
        # 8. Несколько раз сохраняем и открываем как JPEG с низким качеством (если выбрано)
        if "jpeg_compression" in effects_to_apply:
            # Увеличиваем количество итераций компрессии в зависимости от уровня порчи
            compression_iterations = actual_quality_level 
            
            # Более низкое качество JPEG для более высоких уровней порчи
            jpeg_quality_base = max(1, 12 - actual_quality_level * 1.5)
            
            for i in range(compression_iterations):
                buffer = io.BytesIO()
                # Небольшие вариации качества на каждой итерации
                current_quality = max(1, jpeg_quality_base + random.randint(-2, 2))
                img.save(buffer, format='JPEG', quality=int(current_quality))
                buffer.seek(0)
                img = Image.open(buffer)
        
        # Восстанавливаем исходный размер изображения, если он изменился
        if img.size != (original_width, original_height):
            logger.info(f"Восстанавливаем исходный размер изображения: {original_width}x{original_height}")
            try:
                # Используем константы для Pillow >= 9.0
                from PIL.Image import Resampling
                img = img.resize((original_width, original_height), resample=Resampling.LANCZOS)
            except (ImportError, AttributeError):
                try:
                    # Для старых версий PIL, используем константы Pillow
                    img = img.resize((original_width, original_height), resample=Image.LANCZOS)
                except (ImportError, AttributeError):
                    # Fallback для очень старых версий
                    img = img.resize((original_width, original_height), resample=Image.BICUBIC)
        
        # Сохраняем результат в буфер с финальным очень низким качеством
        output_buffer = io.BytesIO()
        final_quality = max(5, 15 - actual_quality_level * 1.5)
        img.save(output_buffer, format='JPEG', quality=int(final_quality))
        output_buffer.seek(0)
        
        logger.info(f"Изображение успешно 'испорчено' с уровнем качества {actual_quality_level}, применены эффекты: {effects_to_apply}")
        return output_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Ошибка при создании JPEG-артефактов: {e}", exc_info=True)
        raise

async def create_meme(image_bytes, text):
    """
    Создает мем из изображения и текста
    
    Args:
        image_bytes (bytes или BytesIO): Байты изображения или объект BytesIO
        text (str): Текст для мема
        
    Returns:
        bytes: Байты изображения с добавленным текстом
    """
    try:
        # Импортируем PIL модули локально для предотвращения проблем с областью видимости при запуске на локальной машине
        from PIL import Image
        
        # Загружаем изображение из байтов
        if isinstance(image_bytes, io.BytesIO):
            image = Image.open(image_bytes)
        else:
            image_stream = io.BytesIO(image_bytes)
            image = Image.open(image_stream)
            
        # Сохраняем оригинальный размер изображения
        original_width, original_height = image.size
        logger.info(f"Оригинальный размер изображения для мема: {original_width}x{original_height}")
        
        # Выбираем позицию текста (можно выбрать случайную для разнообразия)
        positions = ["top", "bottom", "center"]
        position = random.choice(positions)
        
        # Добавляем текст на изображение
        meme_image = add_text_to_image(image, text, position)
        
        # Проверяем, не изменился ли размер изображения и восстанавливаем при необходимости
        if meme_image.size != (original_width, original_height):
            logger.info(f"Восстанавливаем исходный размер изображения для мема: {original_width}x{original_height}")
            try:
                # Используем константы для Pillow >= 9.0
                from PIL.Image import Resampling
                meme_image = meme_image.resize((original_width, original_height), resample=Resampling.LANCZOS)
            except (ImportError, AttributeError):
                try:
                    # Для старых версий PIL, используем константы Pillow
                    meme_image = meme_image.resize((original_width, original_height), resample=Image.LANCZOS)
                except (ImportError, AttributeError):
                    # Fallback для очень старых версий
                    meme_image = meme_image.resize((original_width, original_height), resample=Image.BICUBIC)
        
        # Сохраняем результат в байты
        output_stream = io.BytesIO()
        meme_image.save(output_stream, format=image.format or "JPEG", quality=90)
        output_stream.seek(0)
        
        logger.info(f"Мем успешно создан с текстом в позиции {position}")
        return output_stream.getvalue()
        
    except Exception as e:
        logger.error(f"Ошибка при создании мема: {e}", exc_info=True)
        return None