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
    log_level_str = settings.log_level
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Убираем стандартные обработчики, если они есть
    # for handler in logger.handlers:
    #     logger.removeHandler(handler)

    # Используем stdout
    log_handler = logging.StreamHandler(sys.stdout)

    # Используем наш JSON formatter
    formatter = CustomJsonFormatter('%(timestamp)s %(level)s %(logger)s %(message)s')
    log_handler.setFormatter(formatter)

    # Добавляем обработчик к корневому логгеру
    if not logger.handlers:
        logger.addHandler(log_handler)

    # Настраиваем логгер aiogram (чтобы не дублировался вывод)
    aiogram_logger = logging.getLogger('aiogram')
    aiogram_logger.setLevel(logging.INFO) # Можно сделать более детальным при отладке
    aiogram_logger.propagate = False # Предотвращаем дублирование в корневой логгер
    if not aiogram_logger.handlers:
         aiogram_logger.addHandler(log_handler) # Используем тот же обработчик

    logging.info(f"Logging configured with level: {log_level_str}")

# Вызываем настройку при импорте модуля
# setup_logging() 