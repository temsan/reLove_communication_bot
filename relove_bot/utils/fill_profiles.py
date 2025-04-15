import asyncio
from relove_bot.db.session import SessionLocal
from relove_bot.db.models import User
from relove_bot.rag.pipeline import aggregate_profile_summary
from relove_bot.rag.llm import generate_summary

async def detect_gender(profile_text: str) -> str:
    """
    Определяет пол пользователя по тексту профиля (возвращает 'male', 'female' или 'unknown').
    """
    if not profile_text or not isinstance(profile_text, str) or not profile_text.strip():
        return 'unknown'
    prompt = (
        "Определи пол пользователя (мужской или женский) по следующему профилю. "
        "Ответь только одним словом: 'male' или 'female'. Если не можешь определить — ответь 'unknown'.\n"
        f"Профиль:\n{profile_text}"
    )
    try:
        result = await generate_summary(prompt)
        result = (result or '').lower().strip()
        if result in {'female', 'жен', 'женский'} or 'female' in result or 'жен' in result:
            return 'female'
        if result in {'male', 'муж', 'мужской'} or 'male' in result or 'муж' in result:
            return 'male'
    except Exception as e:
        print(f"[detect_gender] Ошибка определения пола: {e}")
    return 'unknown'

async def select_users(gender: str = None, text_filter: str = None, user_id_list: list = None, rank_by: str = None, limit: int = 30):
    """
    Универсальный отбор пользователей по фильтрам:
    - gender: 'male', 'female', 'unknown', None
    - text_filter: строка (ищет в summary, регистр не важен)
    - user_id_list: список user_id
    - rank_by: поле для сортировки (по context)
    - limit: макс. количество результатов
    Возвращает список словарей: [{id, username, summary, gender, ...}]
    """
    async with SessionLocal() as session:
        users = (await session.execute(User.__table__.select())).fetchall()
        user_objs = []
        for row in users:
            user_id = row.id if hasattr(row, 'id') else row[0]
            if user_id_list and user_id not in user_id_list:
                continue
            user = await session.get(User, user_id)
            if not user:
                continue
            context = user.context or {}
            summary = context.get('last_profile_summary')
            user_gender = context.get('gender')
            # Фильтр по полу
            if gender and user_gender != gender:
                continue
            # Фильтр по тексту
            if text_filter and summary:
                if text_filter.lower() not in summary.lower():
                    continue
            user_dict = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'summary': summary,
                'gender': user_gender,
            }
            user_objs.append((user_dict, context))
        # Ранжирование
        if rank_by:
            def get_rank_val(u):
                val = u[1].get(rank_by)
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return str(val or "")
            user_objs.sort(key=get_rank_val, reverse=True)
        # Ограничение по количеству
        user_objs = user_objs[:limit]
        # Только словари
        return [u[0] for u in user_objs]

# Старый fill_profiles оставляем для CLI-использования (можно вызвать select_users внутри него)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fill/refresh profile summaries and gender for all users.")
    parser.add_argument('--only-female', action='store_true', help='Process only female users')
    args = parser.parse_args()
    asyncio.run(fill_profiles(only_female=args.only_female))
