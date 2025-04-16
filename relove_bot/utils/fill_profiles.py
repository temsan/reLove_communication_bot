import asyncio
from relove_bot.db.session import SessionLocal
from relove_bot.db.models import User
from relove_bot.rag.pipeline import aggregate_profile_summary
from relove_bot.rag.llm import generate_summary

from relove_bot.rag.llm import LLM
from relove_bot.services.telegram_service import client
import base64
from io import BytesIO

async def detect_gender(profile_text: str, user_id: int = None) -> str:
    """
    Определяет пол пользователя по тексту профиля и фото (если user_id передан).
    Всегда анализирует фото, если оно есть.
    """
    if not profile_text or not isinstance(profile_text, str) or not profile_text.strip():
        return 'unknown'
    llm = LLM()
    image_url = None
    if user_id is not None:
        # Берём последнее фото профиля пользователя
        async for photo in client.iter_profile_photos(user_id, limit=1):
            bioio = BytesIO()
            await client.download_media(photo, file=bioio)
            bioio.seek(0)
            img_bytes = bioio.read()
            img_b64 = base64.b64encode(img_bytes).decode()
            image_url = f"data:image/png;base64,{img_b64}"
            break
    prompt = (
        "Определи пол пользователя (мужской или женский) по следующему профилю и, если доступно, по фото. "
        "Ответь только одним словом: 'male' или 'female'. Если не можешь определить — ответь 'unknown'.\n"
        f"Профиль:\n{profile_text}"
    )
    try:
        result = await llm.analyze_content(text=prompt, image_url=image_url, system_prompt="Определи пол пользователя по тексту и фото. Ответь 'male', 'female' или 'unknown' одним словом.", max_tokens=6)
        value = (result["summary"] or '').lower().strip()
        if value in {'female', 'жен', 'женский'} or 'female' in value or 'жен' in value:
            return 'female'
        if value in {'male', 'муж', 'мужской'} or 'male' in value or 'муж' in value:
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
            summary = context.get('summary')
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

# --- Новая асинхронная джоба для массового обновления summary ---
import logging
from relove_bot.rag.llm import LLM

from relove_bot.utils.tg_data import (
    start_client, get_channel_users, get_user_profile,
    get_user_posts_in_channel, get_personal_channel_posts
)
from relove_bot.services.telegram_service import get_full_psychological_summary
from relove_bot.utils.user_utils import save_psychological_summary

async def fill_all_profiles(channel_id: str):
    """
    Для всех пользователей канала:
    - Получает психологический портрет через OpenAI (bio, посты, фото)
    - Сохраняет summary в context пользователя
    """
    logging.info(f"[fill_all_profiles] Старт массового обновления психологических портретов для канала {channel_id}")
    await start_client()
    users = await get_channel_users(channel_id)
    async with SessionLocal() as session:
        for user_id in users:
            user = await session.get(User, user_id)
            if not user:
                continue
            try:
                summary = await get_full_psychological_summary(user_id, main_channel_id=channel_id)
                await save_summary(user_id, summary, session)
                logging.info(f"[fill_all_profiles] Обновлено summary для user_id={user_id}")
                personal_channel_summary = await llm.generate_summary("\n".join(personal_posts))
                # Интеграция анализа фото в общий summary
                # Новый подход: только психологический портрет через OpenAI
                summary = await get_full_psychological_summary(user_id, main_channel_id=channel_id)
                await save_summary(user_id, summary, session)
                logging.info(f"[fill_all_profiles] Обновлено summary для user_id={user_id}")

            except Exception as e:
                logging.error(f"[fill_all_profiles] Ошибка для user_id={user_id}: {e}")
    logging.info(f"[fill_all_profiles] Завершено массовое обновление summary для канала {channel_id}")

# Старый fill_profiles оставляем для CLI-использования (можно вызвать select_users внутри него)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fill/refresh profile summaries and gender for all users.")
    parser.add_argument('--only-female', action='store_true', help='Process only female users')
    args = parser.parse_args()
    asyncio.run(fill_profiles(only_female=args.only_female))
