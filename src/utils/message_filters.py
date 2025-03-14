import re
import logging

logger = logging.getLogger(__name__)

def contains_link(text):
    """Check if text contains links"""
    # Regular expression to match URLs
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+|'
                             r'(?:www\.)+(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+|'
                             r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,6}')
    return bool(url_pattern.search(text))

def contains_mentions(text):
    """Check if text contains mentions (@username)"""
    mention_pattern = re.compile(r'@\w+')
    return bool(mention_pattern.search(text))

def contains_special_characters(text):
    """Check if text contains special characters"""
    # Define which special characters to filter out
    # Here we're excluding common punctuation that would be normal in messages
    special_chars_pattern = re.compile(r'[^\w\s.,!?\'\"«»()-:;]')
    return bool(special_chars_pattern.search(text))

# Функция фильтрации нецензурной лексики была удалена, 
# чтобы разрешить использование такой лексики для генерации текста
def contains_profanity(text):
    """Заглушка для совместимости"""
    return False  # Всегда возвращаем False, чтобы разрешить любые слова

def is_message_valid(text):
    """
    Check if a message is valid according to our filtering rules
    Returns True if message is valid, False otherwise
    """
    if text is None:
        return False
        
    # Check for minimum length (at least 3 characters)
    if len(text) < 3:
        logger.debug("Message too short")
        return False
        
    # Check for links
    if contains_link(text):
        logger.debug("Message contains a link")
        return False
        
    # Check for mentions
    if contains_mentions(text):
        logger.debug("Message contains a mention")
        return False
        
    # Check for special characters
    if contains_special_characters(text):
        logger.debug("Message contains special characters")
        return False
        
    # Check if the message is a command
    if text.startswith('/'):
        logger.debug("Message is a command")
        return False
        
    # If none of the filters caught the message, it's valid
    return True
