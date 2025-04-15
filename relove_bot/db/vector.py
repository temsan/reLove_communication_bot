from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

import logging
qdrant = QdrantClient("localhost", port=6333)

COLLECTION_NAME = "user_profiles"

# Автоматическая инициализация коллекции при импорте
try:
    collections = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION_NAME not in collections:
        qdrant.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
    logging.info(f"[Qdrant] Коллекция '{COLLECTION_NAME}' готова.")
except Exception as e:
    logging.error(f"[Qdrant] Ошибка инициализации коллекции: {e}")

def init_vector_db():
    # Оставлено для явного вызова, если нужно
    try:
        collections = [c.name for c in qdrant.get_collections().collections]
        if COLLECTION_NAME not in collections:
            qdrant.recreate_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
        logging.info(f"[Qdrant] Коллекция '{COLLECTION_NAME}' готова.")
    except Exception as e:
        logging.error(f"[Qdrant] Ошибка инициализации коллекции: {e}")

def upsert_user_embedding(user_id: int, embedding: list[float], metadata: dict):
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

def search_similar_users(query_embedding: list[float], top_k: int = 5):
    hits = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embedding,
        limit=top_k
    )
    return hits
