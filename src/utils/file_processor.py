import logging
import os
import tempfile
from src.utils.message_filters import is_message_valid
from src.database.db_handler import save_filtered_message

logger = logging.getLogger(__name__)

async def process_text_file(file_path, user_id, username, first_name, last_name, chat_id):
    """
    Process a text file line by line, applying message filters
    and saving valid messages to the database
    
    Args:
        file_path (str): Path to the downloaded text file
        user_id (int): User ID who sent the file
        username (str): Username of the sender
        first_name (str): First name of the sender
        last_name (str): Last name of the sender
        chat_id (int): Chat ID where the file was sent
        
    Returns:
        tuple: (total_lines, valid_lines) - count of total and valid lines
    """
    total_lines = 0
    valid_lines = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                total_lines += 1
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Apply message filters
                if is_message_valid(line):
                    # Save valid message to database
                    await save_filtered_message(
                        user_id=user_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        message_text=line,
                        chat_id=chat_id
                    )
                    valid_lines += 1
                    logger.info(f"Saved valid message from file: {line[:30]}...")
                else:
                    logger.debug(f"Filtered out invalid message from file: {line[:30]}...")
    
        logger.info(f"File processing completed. Total lines: {total_lines}, Valid lines: {valid_lines}")
        return total_lines, valid_lines
    
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
        return total_lines, valid_lines

async def download_and_process_file(file, bot, user_id, username, first_name, last_name, chat_id):
    """
    Download a file from Telegram and process it
    
    Args:
        file: Telegram file object
        bot: Bot instance for downloading the file
        user_id (int): User ID who sent the file
        username (str): Username of the sender
        first_name (str): First name of the sender
        last_name (str): Last name of the sender
        chat_id (int): Chat ID where the file was sent
        
    Returns:
        tuple: (success, message, stats) - processing result and statistics
    """
    try:
        # Get file info from Telegram
        file_info = await bot.get_file(file.file_id)
        file_path = file_info.file_path
        
        # Check file extension
        if not file_path.lower().endswith('.txt'):
            return False, "Пожалуйста, прикрепите файл в формате .txt", None
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as temp_file:
            temp_path = temp_file.name
            
        # Download file to temporary location
        await bot.download_file(file_path, destination=temp_path)
        logger.info(f"File downloaded to {temp_path}")
        
        # Process the file
        total_lines, valid_lines = await process_text_file(
            temp_path, user_id, username, first_name, last_name, chat_id
        )
        
        # Clean up the temporary file
        try:
            os.remove(temp_path)
            logger.info(f"Temporary file {temp_path} removed")
        except Exception as e:
            logger.warning(f"Failed to remove temporary file: {e}")
        
        # Prepare stats
        stats = {
            "total_lines": total_lines,
            "valid_lines": valid_lines,
            "invalid_lines": total_lines - valid_lines
        }
        
        return True, "Файл успешно обработан", stats
    
    except Exception as e:
        logger.error(f"Error downloading and processing file: {e}", exc_info=True)
        return False, "Произошла ошибка при обработке файла", None