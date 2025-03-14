import logging
from src.config import ALLOWED_GROUP_CHAT_ID, ADMIN_USER_ID
from src.database.db_handler import add_allowed_user, is_user_allowed, remove_allowed_user

logger = logging.getLogger(__name__)

async def process_group_member(user_id, username, first_name, last_name):
    """
    Process a user from the allowed group chat
    Add them to the database of allowed users
    
    Args:
        user_id (int): User ID
        username (str): Username
        first_name (str): First name
        last_name (str): Last name
    """
    logger.info(f"Processing group member: {user_id} ({username})")
    await add_allowed_user(user_id, username, first_name, last_name)

async def check_chat_access(chat_id, user_id=None):
    """
    Check if the chat is allowed for bot operation
    
    Args:
        chat_id (int): Chat ID
        user_id (int, optional): User ID. Default is None.
        
    Returns:
        bool: True if access is allowed, False otherwise
    """
    # Если это пользователь-администратор, всегда даем доступ
    if user_id and user_id == ADMIN_USER_ID:
        logger.debug(f"Access granted for admin user: {user_id}")
        return True
        
    # Если это основной разрешенный групповой чат
    if chat_id == ALLOWED_GROUP_CHAT_ID:
        logger.debug(f"Access granted for main group chat: {chat_id}")
        return True
        
    # Если это личный чат с пользователем
    if chat_id > 0 and user_id:
        # Проверяем, есть ли пользователь в списке разрешенных
        allowed = await is_user_allowed(user_id)
        logger.debug(f"Private chat with user {user_id}, access: {allowed}")
        return allowed
        
    # В других случаях (другие группы и т.д.) доступ запрещен
    logger.debug(f"Access denied for chat {chat_id}")
    return False

async def check_admin_rights(user_id):
    """
    Проверяет, является ли пользователь администратором
    
    Args:
        user_id (int): ID пользователя
        
    Returns:
        bool: True если пользователь админ, False в противном случае
    """
    return user_id == ADMIN_USER_ID

async def manually_add_user(user_id, username=None, first_name=None, last_name=None):
    """
    Добавляет пользователя в список разрешенных вручную (административная функция)
    
    Args:
        user_id (int): ID пользователя
        username (str, optional): Имя пользователя
        first_name (str, optional): Имя
        last_name (str, optional): Фамилия
        
    Returns:
        bool: True если пользователь успешно добавлен, False в противном случае
    """
    try:
        # Проверяем, указан ли корректный ID пользователя
        if not user_id or not isinstance(user_id, int) or user_id <= 0:
            logger.error(f"Invalid user ID: {user_id}")
            return False
            
        # Устанавливаем значения по умолчанию для отсутствующих параметров
        username = username or f"user_{user_id}"
        first_name = first_name or "Unknown"
        last_name = last_name or ""
        
        # Добавляем пользователя в базу данных
        await add_allowed_user(user_id, username, first_name, last_name)
        logger.info(f"Manually added user to allowed list: {user_id} ({username})")
        return True
    except Exception as e:
        logger.error(f"Error adding user {user_id} to allowed list: {e}")
        return False
        
async def manually_remove_user(user_id):
    """
    Удаляет пользователя из списка разрешенных вручную (административная функция)
    
    Args:
        user_id (int): ID пользователя
        
    Returns:
        bool: True если пользователь успешно удален, False в противном случае
    """
    try:
        # Проверяем, указан ли корректный ID пользователя
        if not user_id or not isinstance(user_id, int) or user_id <= 0:
            logger.error(f"Invalid user ID for removal: {user_id}")
            return False
        
        # Удаляем пользователя из базы данных
        result = await remove_allowed_user(user_id)
        if result:
            logger.info(f"Manually removed user from allowed list: {user_id}")
        else:
            logger.warning(f"Failed to remove user {user_id} from allowed list")
        return result
    except Exception as e:
        logger.error(f"Error removing user {user_id} from allowed list: {e}")
        return False