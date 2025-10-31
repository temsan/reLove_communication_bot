import logging

logger = logging.getLogger(__name__)

# Qdrant опционален - обрабатываем отсутствие
qdrant = None
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, VectorParams, PointStruct
    qdrant = QdrantClient("localhost", port=6333)
    logger.info("[Qdrant] Клиент инициализирован")
except ImportError:
    logger.warning("[Qdrant] Библиотека qdrant-client не установлена. Команда /similar недоступна.")
except Exception as e:
    logger.warning(f"[Qdrant] Ошибка инициализации: {e}. Команда /similar недоступна.")

COLLECTION_NAME = "user_profiles"

# Автоматическая инициализация коллекции при импорте
if qdrant:
    try:
        collections = [c.name for c in qdrant.get_collections().collections]
        if COLLECTION_NAME not in collections:
            qdrant.recreate_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
        logger.info(f"[Qdrant] Коллекция '{COLLECTION_NAME}' готова.")
    except Exception as e:
        logger.error(f"[Qdrant] Ошибка инициализации коллекции: {e}")
        qdrant = None  # Отключаем Qdrant при ошибке

def init_vector_db():
    """Инициализирует векторную БД (оставлено для явного вызова, если нужно)"""
    global qdrant
    if not qdrant:
        logger.warning("[Qdrant] Клиент недоступен. Убедитесь, что Qdrant запущен и qdrant-client установлен.")
        return False
    try:
        collections = [c.name for c in qdrant.get_collections().collections]
        if COLLECTION_NAME not in collections:
            qdrant.recreate_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
        logger.info(f"[Qdrant] Коллекция '{COLLECTION_NAME}' готова.")
        return True
    except Exception as e:
        logger.error(f"[Qdrant] Ошибка инициализации коллекции: {e}")
        qdrant = None
        return False

def upsert_user_embedding(user_id: int, embedding: list[float], metadata: dict):
    """Сохраняет эмбеддинг пользователя в Qdrant (опционально)"""
    if not qdrant:
        logger.debug(f"[Qdrant] Пропуск сохранения для {user_id} - Qdrant недоступен")
        return
    try:
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=user_id,
                    vector=embedding,
                    payload=metadata
                )
            ]
        )
    except Exception as e:
        logger.error(f"[Qdrant] Ошибка сохранения эмбеддинга для {user_id}: {e}")

def search_similar_users(query_embedding: list[float], top_k: int = 5):
    """Ищет похожих пользователей в Qdrant (опционально)"""
    if not qdrant:
        logger.debug("[Qdrant] Поиск недоступен - Qdrant не запущен")
        return []
    try:
        hits = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            limit=top_k
        )
        return hits
    except Exception as e:
        logger.error(f"[Qdrant] Ошибка поиска: {e}")
        return []
