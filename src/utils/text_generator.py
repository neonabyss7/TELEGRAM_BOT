import re
import random
import logging
import asyncio
import markovify
from collections import defaultdict
from src.database.db_handler import Database

logger = logging.getLogger(__name__)

# Словарь для хранения модели Маркова (наша реализация)
markov_model = defaultdict(list)
# Модель на основе markovify
markovify_model = None
# Семафор для синхронизации доступа к модели Маркова
# Предотвратит одновременное обновление модели несколькими процессами
model_lock = asyncio.Semaphore(1)
# Список запрещенных окончаний предложений
forbidden_endings = [
    # Союзы
    'и', 'или', 'но', 'а', 'да', 'либо', 'зато', 'однако', 'хотя', 'что', 'чтобы', 'если', 'пока', 'когда', 
    # Предлоги
    'в', 'на', 'под', 'над', 'за', 'перед', 'через', 'к', 'от', 'из', 'с', 'у', 'о', 'об', 'про', 'по', 'до',
    # Частицы 
    'же', 'бы', 'ли', 'ведь', 'вот', 'ну', 'не', 'ни', 'даже', 'лишь', 'только', 'аж',
    # Междометия
    'ой', 'ах', 'ой', 'эх', 'увы', 'ух', 'ура',
    # Другие слова, которые не должны заканчивать предложение
    'это', 'как', 'так', 'где', 'куда', 'откуда', 'который', 'которая', 'которое', 'которые',
    'чей', 'чья', 'чьё', 'чьи', 'какой', 'какая', 'какое', 'какие', 'мой', 'твой', 'его', 'её', 'наш', 'ваш', 'их'
]

def tokenize_text(text):
    """Разбивает текст на токены (слова)"""
    # Удаляем специальные символы, кроме точек, запятых и пробелов
    text = re.sub(r'[^\w\s.,!?]', '', text.lower())
    return re.findall(r'\w+|[.,!?]', text)

async def update_markov_model():
    """Обновляет модель Маркова на основе собранных сообщений из базы данных"""
    global markov_model, markovify_model
    
    # Используем семафор с таймаутом для предотвращения блокировки
    # Если семафор занят более 0.1 секунды, то просто продолжаем выполнение
    try:
        # Пробуем получить блокировку с таймаутом
        await asyncio.wait_for(model_lock.acquire(), timeout=0.1)
        
        try:
            logger.info("Начато обновление модели Маркова")
            temp_model = defaultdict(list)
            
            # Подключаемся к базе данных
            db = Database()
            await db.connect()
            
            # Получаем все сообщения из базы данных
            async with db.conn.execute("SELECT message_text FROM messages") as cursor:
                messages = await cursor.fetchall()
            
            # Закрываем соединение с базой данных
            await db.disconnect()
            
            # Если сообщений нет, выходим
            if not messages:
                logger.warning("No messages found in database to build Markov model")
                return
            
            # Строим нашу собственную модель Маркова
            for message in messages:
                tokens = tokenize_text(message[0])
                if len(tokens) < 2:
                    continue
                
                # Создаем пары слов для модели Маркова
                for i in range(len(tokens) - 1):
                    temp_model[tokens[i]].append(tokens[i + 1])
            
            # Создаем модель с использованием библиотеки markovify
            try:
                # Подготавливаем сообщения для markovify
                # Нужно, чтобы каждое сообщение было полным предложением
                processed_messages = []
                for msg in messages:
                    text = msg[0].strip()
                    # Добавляем точку в конце, если ее нет
                    if text and not text[-1] in ['.', '!', '?']:
                        text += '.'
                    # Проверяем, что текст имеет достаточную длину
                    if len(text.split()) >= 3:
                        processed_messages.append(text)
                
                # Объединяем подготовленные сообщения в один текст для markovify
                new_markovify_model = None
                if processed_messages:
                    all_messages_text = "\n".join(processed_messages)
                    
                    # Создаем модель markovify с более подходящим state_size для русского языка
                    # state_size=2 дает более естественные пары слов, но сохраняет разнообразие
                    new_markovify_model = markovify.Text(all_messages_text, state_size=2)
                    logger.info("Markovify model created successfully")
                else:
                    logger.warning("No suitable messages for markovify model")
            
                # Обновляем глобальные переменные только в случае успеха
                markov_model = temp_model
                markovify_model = new_markovify_model
                logger.info(f"Markov model updated with {len(messages)} messages")
                
            except Exception as e:
                logger.error(f"Error creating markovify model: {e}", exc_info=True)
                
        except Exception as e:
            logger.error(f"Error updating Markov model: {e}", exc_info=True)
        finally:
            # Всегда освобождаем семафор
            model_lock.release()
            
    except asyncio.TimeoutError:
        logger.info("Пропущено обновление модели Маркова, так как другое обновление уже выполняется")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обновлении модели: {e}", exc_info=True)

def capitalize_first_letter(text):
    """Делает первую букву текста заглавной"""
    if not text:
        return text
    return text[0].upper() + text[1:]

def generate_sentence_custom(min_words=8, max_words=20):
    """Генерирует предложение, используя нашу собственную реализацию модели Маркова"""
    try:
        # Проверяем наличие данных в модели
        if not markov_model:
            return "У меня еще нет данных для генерации текста."
        
        # Создаем базовое предложение из примеров для стабильности
        base_sentences = [
            "Интересный факт о том, что в мире много интересного.",
            "Знаете ли вы, что каждый день происходит что-то новое.",
            "Мысли о будущем всегда вызывают разные эмоции у людей.",
            "В прошлом веке технологии развивались стремительно.",
            "Путешествие в горы дарит незабываемые впечатления.",
            "Современная литература предлагает много интересных идей.",
            "История человечества полна удивительных открытий.",
            "Наука не стоит на месте и постоянно развивается."
        ]
        
        # Если у нас достаточно слов в модели, генерируем настоящее предложение
        if len(markov_model) > 50:
            # Выбираем любое слово, начинающееся с буквы, для начала предложения
            start_words = [word for word in markov_model.keys() 
                         if word and word[0].isalpha() and word not in forbidden_endings]
            
            if not start_words:
                # Если нет подходящих слов, берем случайное заготовленное предложение
                return random.choice(base_sentences)
            
            # Выбираем случайное начальное слово
            current = random.choice(start_words)
            
            # Начинаем предложение
            words = [current.capitalize()]
            length = 1
            
            # Генерируем предложение нужной длины
            while length < max_words:
                if current not in markov_model or not markov_model[current]:
                    break
                
                next_word = random.choice(markov_model[current])
                
                # Добавляем слово
                words.append(next_word)
                current = next_word
                
                # Увеличиваем счетчик длины для слов (не знаков препинания)
                if next_word.isalpha():
                    length += 1
                
                # Если встретили знак окончания предложения и достигли минимальной длины
                if next_word in ['.', '!', '?'] and length >= min_words:
                    break
            
            # Убеждаемся, что предложение заканчивается точкой
            if not words[-1] in ['.', '!', '?']:
                words.append('.')
            
            # Формируем итоговое предложение
            sentence = ' '.join(words)
            # Исправляем пунктуацию
            sentence = sentence.replace(' ,', ',').replace(' .', '.').replace(' !', '!').replace(' ?', '?')
            
            return sentence
            
        else:
            # Если недостаточно данных, возвращаем заготовленное предложение
            return random.choice(base_sentences)
            
    except Exception as e:
        logger.error(f"Ошибка при генерации предложения: {e}", exc_info=True)
        return "Интересно, что природа всегда находит способ удивить нас своей красотой."

def generate_sentence_markovify(attempts=15, max_overlap_ratio=0.4):
    """Генерирует предложение с использованием библиотеки markovify"""
    if not markovify_model:
        return generate_sentence_custom()  # Вернуться к нашей реализации, если markovify не работает
    
    # Пробуем сгенерировать предложение несколько раз с ограничением на перекрытие
    # max_overlap_ratio ограничивает количество последовательных слов, которые могут быть взяты из исходного текста
    # Уменьшение max_overlap_ratio и увеличение попыток уменьшает шанс плагиата целых предложений
    for _ in range(attempts):
        sentence = markovify_model.make_sentence(tries=100, max_overlap_ratio=max_overlap_ratio)
        if sentence:
            # Проверяем, что последнее слово не союз, предлог или частица
            words = sentence.split()
            if words and words[-1].lower().rstrip('.!?') not in forbidden_endings:
                # Всегда делаем первую букву заглавной
                return capitalize_first_letter(sentence)
    
    # Если не удалось сгенерировать предложение через markovify, используем нашу реализацию
    return generate_sentence_custom(min_words=8, max_words=20)

def generate_sentence(min_words=8, max_words=20):
    """Генерирует предложение, используя комбинированный подход"""
    
    try:
        # Случайно выбираем, какой метод использовать
        if random.random() < 0.7 and markovify_model:  # 70% времени используем markovify, если он доступен
            sentence = generate_sentence_markovify()
        else:
            sentence = generate_sentence_custom(min_words=min_words, max_words=max_words)
        
        # Проверяем длину предложения, чтобы оно не было слишком коротким
        words = sentence.split()
        if len(words) < min_words:
            # Если слишком короткое, попробуем другой метод вместо рекурсии
            if random.random() < 0.5:
                sentence = generate_sentence_markovify()
            else:
                sentence = generate_sentence_custom(min_words=min_words, max_words=max_words)
            
            # Проверяем ещё раз
            words = sentence.split()
            if len(words) < min_words:
                # Если всё ещё короткая, используем custom метод с увеличенными параметрами
                sentence = generate_sentence_custom(min_words=min_words, max_words=30)
        
        return sentence
    except Exception as e:
        logger.error(f"Ошибка при генерации предложения: {e}", exc_info=True)
        return "Произошла ошибка при генерации текста. Пожалуйста, попробуйте ещё раз."

def generate_story(min_sentences=2, max_sentences=5, min_words=8, max_words=20):
    """Генерирует историю из нескольких предложений"""
    try:
        # Генерируем не менее 2 предложений для истории
        num_sentences = random.randint(min_sentences, max_sentences)
        sentences = []
        
        for _ in range(num_sentences):
            sentence = generate_sentence(min_words=min_words, max_words=max_words)
            sentences.append(sentence)
        
        # Проверяем, что у нас есть хотя бы одно предложение
        if not sentences:
            sentences = ["Генерация истории не удалась. Пожалуйста, попробуйте снова."]
        
        return ' '.join(sentences)
    except Exception as e:
        logger.error(f"Ошибка при генерации истории: {e}", exc_info=True)
        return "Произошла ошибка при генерации истории. Пожалуйста, попробуйте ещё раз."