import sqlite3
import logging
import os
import asyncio
from datetime import datetime
import aiosqlite

from src.config import DATABASE_NAME

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name=DATABASE_NAME):
        self.db_name = db_name
        self.conn = None

    async def connect(self):
        # Using aiosqlite for proper async database operations
        self.conn = await aiosqlite.connect(self.db_name)
        logger.info(f"Connected to database: {self.db_name}")

    async def disconnect(self):
        if self.conn:
            await self.conn.close()
            logger.info("Disconnected from database")

    async def create_tables(self):
        create_messages_table = '''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            message_text TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            timestamp DATETIME NOT NULL
        )
        '''
        
        create_stickers_table = '''
        CREATE TABLE IF NOT EXISTS stickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sticker_id TEXT NOT NULL,
            file_id TEXT NOT NULL UNIQUE,
            set_name TEXT,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            timestamp DATETIME NOT NULL
        )
        '''
        
        create_animations_table = '''
        CREATE TABLE IF NOT EXISTS animations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animation_id TEXT NOT NULL,
            file_id TEXT NOT NULL UNIQUE,
            file_name TEXT,
            mime_type TEXT,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            timestamp DATETIME NOT NULL
        )
        '''
        
        create_allowed_users_table = '''
        CREATE TABLE IF NOT EXISTS allowed_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            timestamp DATETIME NOT NULL
        )
        '''
        
        await self.conn.execute(create_messages_table)
        await self.conn.execute(create_stickers_table)
        await self.conn.execute(create_animations_table)
        await self.conn.execute(create_allowed_users_table)
        await self.conn.commit()
        logger.info("Database tables created or already exist")

    async def save_message(self, user_id, username, first_name, last_name, message_text, chat_id):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = '''
        INSERT INTO messages (user_id, username, first_name, last_name, message_text, chat_id, timestamp) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        params = (user_id, username, first_name, last_name, message_text, chat_id, timestamp)
        
        try:
            if not self.conn:
                logger.warning("Connection not established, connecting...")
                await self.connect()
                
            await self.conn.execute(query, params)
            await self.conn.commit()
            logger.info(f"Message from user {user_id} saved to database")
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            raise
        
    async def save_sticker(self, sticker_id, file_id, set_name, user_id, chat_id):
        """Save a sticker to the database"""
        try:
            if not self.conn:
                logger.warning("Connection not established, connecting...")
                await self.connect()
                
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Проверяем, есть ли уже такой стикер в базе
            check_query = "SELECT id FROM stickers WHERE file_id = ?"
            cursor = await self.conn.execute(check_query, (file_id,))
            existing = await cursor.fetchone()
            await cursor.close()
            
            # Если стикер уже есть, не добавляем его повторно
            if existing:
                logger.debug(f"Sticker with file_id {file_id} already exists in database")
                return False
                
            # Вставляем новый стикер
            query = '''
            INSERT INTO stickers (sticker_id, file_id, set_name, user_id, chat_id, timestamp) 
            VALUES (?, ?, ?, ?, ?, ?)
            '''
            params = (sticker_id, file_id, set_name, user_id, chat_id, timestamp)
            
            await self.conn.execute(query, params)
            await self.conn.commit()
            logger.info(f"Sticker {sticker_id} from user {user_id} saved to database")
            return True
        except Exception as e:
            logger.error(f"Error saving sticker: {e}")
            raise
        
    async def get_random_sticker(self):
        """Get a random sticker from the database"""
        try:
            if not self.conn:
                logger.warning("Connection not established, connecting...")
                await self.connect()
                
            query = "SELECT file_id FROM stickers ORDER BY RANDOM() LIMIT 1"
            cursor = await self.conn.execute(query)
            result = await cursor.fetchone()
            await cursor.close()
            
            if result:
                return result[0]  # Возвращаем file_id
            return None
        except Exception as e:
            logger.error(f"Error getting random sticker: {e}")
            return None
        
    async def save_animation(self, animation_id, file_id, file_name, mime_type, user_id, chat_id):
        """Save an animation to the database"""
        try:
            if not self.conn:
                logger.warning("Connection not established, connecting...")
                await self.connect()
                
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Проверяем, есть ли уже такая анимация в базе
            check_query = "SELECT id FROM animations WHERE file_id = ?"
            cursor = await self.conn.execute(check_query, (file_id,))
            existing = await cursor.fetchone()
            await cursor.close()
            
            # Если анимация уже есть, не добавляем её повторно
            if existing:
                logger.debug(f"Animation with file_id {file_id} already exists in database")
                return False
                
            # Вставляем новую анимацию
            query = '''
            INSERT INTO animations (animation_id, file_id, file_name, mime_type, user_id, chat_id, timestamp) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
            params = (animation_id, file_id, file_name, mime_type, user_id, chat_id, timestamp)
            
            await self.conn.execute(query, params)
            await self.conn.commit()
            logger.info(f"Animation {animation_id} from user {user_id} saved to database")
            return True
        except Exception as e:
            logger.error(f"Error saving animation: {e}")
            raise
        
    async def get_random_animation(self):
        """Get a random animation from the database"""
        try:
            if not self.conn:
                logger.warning("Connection not established, connecting...")
                await self.connect()
                
            query = "SELECT file_id FROM animations ORDER BY RANDOM() LIMIT 1"
            cursor = await self.conn.execute(query)
            result = await cursor.fetchone()
            await cursor.close()
            
            if result:
                return result[0]  # Возвращаем file_id
            return None
        except Exception as e:
            logger.error(f"Error getting random animation: {e}")
            return None
        
    async def fetch_all(self, query, params=None):
        """Execute a query and fetch all results"""
        try:
            if not self.conn:
                logger.warning("Connection not established, connecting...")
                await self.connect()
                
            if params:
                cursor = await self.conn.execute(query, params)
            else:
                cursor = await self.conn.execute(query)
                
            rows = await cursor.fetchall()
            await cursor.close()
            return rows
        except Exception as e:
            logger.error(f"Database error in fetch_all: {e}")
            return []
            
    async def get_stats(self):
        """Get database statistics: messages count, unique words count, stickers count, animations count"""
        stats = {}
        
        try:
            if not self.conn:
                logger.warning("Connection not established, connecting...")
                await self.connect()
                
            # Get messages count
            query = "SELECT COUNT(*) FROM messages"
            cursor = await self.conn.execute(query)
            result = await cursor.fetchone()
            await cursor.close()
            stats['messages_count'] = result[0] if result else 0
            
            # Получаем все сообщения для подсчета уникальных слов
            query = """
            SELECT message_text FROM messages
            """
            try:
                cursor = await self.conn.execute(query)
                rows = await cursor.fetchall()
                await cursor.close()
                
                # Создаем множество для хранения уникальных слов
                unique_words = set()
                
                # Проходим по всем сообщениям и разбиваем их на слова
                for row in rows:
                    if row[0]:  # Проверяем, что сообщение не пустое
                        # Разбиваем текст на слова (знаки препинания удаляются, все в нижнем регистре)
                        words = row[0].lower().replace('.', ' ').replace(',', ' ').replace('!', ' ').replace('?', ' ') \
                                 .replace(':', ' ').replace(';', ' ').replace('(', ' ').replace(')', ' ') \
                                 .replace('-', ' ').replace('"', ' ').replace("'", ' ').split()
                        
                        # Добавляем слова в множество
                        for word in words:
                            if len(word) > 1:  # Игнорируем однобуквенные слова
                                unique_words.add(word)
                
                # Количество уникальных слов - это размер множества
                stats['unique_words_count'] = len(unique_words)
                logger.info(f"Подсчитано {len(unique_words)} уникальных слов из {len(rows)} сообщений")
                
            except Exception as e:
                logger.error(f"Ошибка при подсчете уникальных слов: {e}")
                # Если произошла ошибка, используем резервный вариант
                stats['unique_words_count'] = stats['messages_count'] * 8
            
            # Get stickers count
            query = "SELECT COUNT(*) FROM stickers"
            cursor = await self.conn.execute(query)
            result = await cursor.fetchone()
            await cursor.close()
            stats['stickers_count'] = result[0] if result else 0
            
            # Get animations count
            query = "SELECT COUNT(*) FROM animations"
            cursor = await self.conn.execute(query)
            result = await cursor.fetchone()
            await cursor.close()
            stats['animations_count'] = result[0] if result else 0
            
            return stats
        except Exception as e:
            logger.error(f"Database error in get_stats: {e}")
            return {
                'messages_count': 0,
                'unique_words_count': 0,
                'stickers_count': 0,
                'animations_count': 0
            }

# Singleton instance
db = Database()

async def init_db():
    """Initialize the database connection and create tables"""
    await db.connect()
    await db.create_tables()
    logger.info("Database initialized")

async def save_filtered_message(user_id, username, first_name, last_name, message_text, chat_id):
    """Save a filtered message to the database"""
    try:
        await db.connect()
        await db.save_message(user_id, username, first_name, last_name, message_text, chat_id)
    finally:
        await db.disconnect()
    
async def save_sticker_to_db(sticker_id, file_id, set_name, user_id, chat_id):
    """Save a sticker to the database"""
    try:
        await db.connect()
        return await db.save_sticker(sticker_id, file_id, set_name, user_id, chat_id)
    finally:
        await db.disconnect()
    
async def get_random_sticker_from_db():
    """Get a random sticker from the database"""
    try:
        await db.connect()
        return await db.get_random_sticker()
    finally:
        await db.disconnect()
    
async def save_animation_to_db(animation_id, file_id, file_name, mime_type, user_id, chat_id):
    """Save an animation to the database"""
    try:
        await db.connect()
        return await db.save_animation(animation_id, file_id, file_name, mime_type, user_id, chat_id)
    finally:
        await db.disconnect()
    
async def get_random_animation_from_db():
    """Get a random animation from the database"""
    try:
        await db.connect()
        return await db.get_random_animation()
    finally:
        await db.disconnect()
    
async def get_database_stats():
    """Get database statistics"""
    await db.connect()
    stats = await db.get_stats()
    await db.disconnect()
    return stats
    
async def get_all_messages():
    """Get all messages from the database for export"""
    await db.connect()
    try:
        query = "SELECT message_text FROM messages ORDER BY id"
        rows = await db.fetch_all(query)
        messages = [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Error getting all messages: {e}")
        messages = []
    finally:
        await db.disconnect()
    return messages

async def add_allowed_user(user_id, username, first_name, last_name):
    """Add or update user in the allowed users list"""
    await db.connect()
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Используем UPSERT (INSERT OR REPLACE) для добавления или обновления пользователя
        query = '''
        INSERT OR REPLACE INTO allowed_users (user_id, username, first_name, last_name, timestamp)
        VALUES (?, ?, ?, ?, ?)
        '''
        params = (user_id, username, first_name, last_name, timestamp)
        
        await db.conn.execute(query, params)
        await db.conn.commit()
        logger.info(f"User {user_id} ({username}) added to allowed users list")
        return True
    except Exception as e:
        logger.error(f"Error adding user to allowed list: {e}")
        return False
    finally:
        await db.disconnect()

async def is_user_allowed(user_id):
    """Check if user is in the allowed users list"""
    await db.connect()
    try:
        query = "SELECT user_id FROM allowed_users WHERE user_id = ?"
        rows = await db.fetch_all(query, (user_id,))
        is_allowed = len(rows) > 0
        logger.debug(f"User {user_id} allowed status: {is_allowed}")
        return is_allowed
    except Exception as e:
        logger.error(f"Error checking if user is allowed: {e}")
        return False
    finally:
        await db.disconnect()
        
async def remove_allowed_user(user_id):
    """Remove user from the allowed users list"""
    await db.connect()
    try:
        # Проверяем, существует ли пользователь
        check_query = "SELECT user_id FROM allowed_users WHERE user_id = ?"
        rows = await db.fetch_all(check_query, (user_id,))
        if not rows:
            logger.warning(f"User {user_id} not found in allowed users list")
            return False
            
        # Удаляем пользователя
        query = "DELETE FROM allowed_users WHERE user_id = ?"
        await db.conn.execute(query, (user_id,))
        await db.conn.commit()
        logger.info(f"User {user_id} removed from allowed users list")
        return True
    except Exception as e:
        logger.error(f"Error removing user from allowed list: {e}")
        return False
    finally:
        await db.disconnect()
        
async def disconnect_db():
    """Закрывает соединение с базой данных на уровне модуля"""
    global db
    
    try:
        if db:
            logger.info("Закрытие соединения с базой данных...")
            await db.disconnect()
            logger.info("Соединение с базой данных успешно закрыто")
        return True
    except Exception as e:
        logger.error(f"Ошибка при закрытии соединения с базой данных: {e}")
        return False
