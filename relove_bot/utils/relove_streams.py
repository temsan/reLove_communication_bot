import logging
from relove_bot.services.llm_service import LLMService

logger = logging.getLogger(__name__)

async def detect_relove_streams(user, summary=None):
    """
    Определяет список пройденных потоков reLove для пользователя по summary или полям профиля.
    Возвращает список строк (названия потоков).
    """
    if not summary:
        summary = getattr(user, 'profile_summary', None) or ''
    prompt = f"Определи, какие потоки reLove прошёл пользователь на основе его профиля. Перечисли только названия потоков через запятую.\nПрофиль: {summary}"
    llm = LLMService()
    try:
        streams_str = await llm.analyze_text(prompt, system_prompt="Определи потоки пользователя", max_tokens=16)
        streams = [s.strip().capitalize() for s in streams_str.split(',') if s.strip()]
        logger.info(f"Обнаружены потоки для user {getattr(user, 'id', None)}: {streams}")
        return streams
    except Exception as e:
        logger.warning(f"Не удалось определить потоки reLove для пользователя {getattr(user, 'id', None)}: {e}")
        return []

async def detect_relove_streams_by_posts(posts: list) -> dict:
    """
    Определяет потоки reLove по постам пользователя.
    Возвращает словарь с двумя списками:
    - 'interest': потоки, которые упоминались или проявлен интерес
    - 'completed': потоки, которые пользователь явно проходил
    """
    if not posts:
        return {'interest': [], 'completed': []}
    try:
        posts_text = '\n'.join(posts)
        prompt = (
            "В reLove есть потоки: Мужской, Женский, Смешанный, Путь Героя.\n"
            "Проанализируй посты пользователя.\n"
            "1. Сначала укажи, какие потоки из этого списка хоть как-то упоминались пользователем или к ним проявлен интерес.\n"
            "2. Затем отдельно укажи, какие потоки пользователь явно проходил (есть прямые или косвенные признаки завершения/участия).\n"
            "Ответ верни в формате JSON: {\"interest\": [...], \"completed\": [...]}\n"
            "Посты пользователя:\n" + posts_text
        )
        llm = LLMService()
        result_str = await llm.analyze_text(prompt, system_prompt="Определи потоки пользователя", max_tokens=64)
        import json
        try:
            result = json.loads(result_str)
            interest = [s.strip().capitalize() for s in result.get('interest', []) if s.strip()]
            completed = [s.strip().capitalize() for s in result.get('completed', []) if s.strip()]
        except Exception as e:
            logger.warning(f"Не удалось распарсить JSON от LLM: {e}. Ответ: {result_str}")
            interest = []
            completed = []
        logger.info(f"Потоки по постам: интерес={interest}, прохождение={completed}")
        return {'interest': interest, 'completed': completed}
    except Exception as e:
        logger.warning(f"Не удалось определить потоки reLove по постам: {e}")
        return {'interest': [], 'completed': []}
