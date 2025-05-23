import logging
import sys
from pythonjsonlogger import jsonlogger
from .config import settings

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            # Добавляем временную метку в стандартном формате ISO
            log_record['timestamp'] = record.created
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
        # Добавляем имя логгера
        log_record['logger'] = record.name

def setup_logging():
    """Configures logging for the application to output JSON to stdout."""
    # Устанавливаем уровень логирования по умолчанию WARNING вместо INFO
    log_level = logging.WARNING
    
    # Создаем форматтер
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Настраиваем корневой логгер
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Удаляем все существующие обработчики
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Добавляем консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Настраиваем логгеры для внешних библиотек
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Отключаем логирование для ненужных модулей
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)

# Вызываем настройку при импорте модуля -- УДАЛЯЕМ ЭТО
# setup_logging()