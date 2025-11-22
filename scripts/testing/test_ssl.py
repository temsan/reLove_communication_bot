#!/usr/bin/env python3
import ssl
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def check_ssl():
    try:
        # Проверяем доступность SSL
        ssl_context = ssl.create_default_context()
        logger.info("SSL контекст успешно создан")
        
        # Проверяем версию OpenSSL
        logger.info(f"Версия OpenSSL: {ssl.OPENSSL_VERSION}")
        
        # Проверяем доступные протоколы
        protocols = [
            'PROTOCOL_TLS', 'PROTOCOL_TLS_CLIENT', 'PROTOCOL_TLS_SERVER',
            'PROTOCOL_SSLv23', 'OP_NO_SSLv2', 'OP_NO_SSLv3', 'OP_NO_TLSv1',
            'OP_NO_TLSv1_1', 'HAS_ALPN'
        ]
        
        for proto in protocols:
            if hasattr(ssl, proto):
                logger.debug(f"{proto}: {getattr(ssl, proto)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при проверке SSL: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("Проверка SSL...")
    if check_ssl():
        logger.info("Проверка SSL завершена успешно")
    else:
        logger.error("Обнаружены проблемы с SSL")
