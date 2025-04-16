import logging
from aiogram import Router, types
from aiogram.filters import Command
from ..rag.llm import generate_summary, generate_rag_answer
from ..rag.pipeline import get_user_context
from ..db.session import SessionLocal
from ..db.models import UserActivityLog, User
from datetime import datetime

logger = logging.getLogger(__name__)
router = Router()

from ..rag.pipeline import get_profile_summary
from ..db.vector import search_similar_users
from ..rag.llm import get_text_embedding
from ..utils.fill_profiles import select_users
import logging

# Список Telegram user_id админов
ADMIN_IDS = {123456789, 987654321}  # Замените на свои id

from relove_bot.utils.fill_profiles import fill_all_profiles
from relove_bot.config import settings
import asyncio

@router.message(commands=["admin_update_summaries"])
async def handle_admin_update_summaries(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("Нет доступа. Только для администраторов.")
        return
    await message.reply("Обновление summary пользователей запущено!")
    # Запуск в фоне, чтобы не блокировать бота
    asyncio.create_task(fill_all_profiles(settings.channel_id))
    await message.reply("Обновление запущено в фоне. Результат будет доступен в логах.")

@router.message(commands=["admin_find_users"])
async def handle_admin_find_users(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("Нет доступа. Только для администраторов.")
        return
    args = message.get_args() if hasattr(message, 'get_args') else message.text[len("/admin_find_users"):].strip()
    # Парсим фильтры: gender=, текст=, rank_by=, limit=
    filters = {}
    for part in args.split():
        if '=' in part:
            k, v = part.split('=', 1)
            filters[k.strip()] = v.strip()
    gender = filters.get('gender')
    text_filter = filters.get('текст') or filters.get('text')
    rank_by = filters.get('rank_by')
    try:
        limit = int(filters.get('limit', 20))
    except Exception:
        limit = 20
    # Выборка пользователей
    try:
        users = await select_users(gender=gender, text_filter=text_filter, rank_by=rank_by, limit=limit)
        if not users:
            await message.reply("Пользователи не найдены по заданным фильтрам.")
            return
        lines = [f"id | username | gender | summary"]
        for u in users:
            lines.append(f"{u['id']} | @{u['username']} | {u['gender']} | {(u['summary'] or '')[:60]}")
        text = '\n'.join(lines)
        if len(text) > 4000:
            text = text[:3990] + '\n...'
        await message.reply(text)
    except Exception as e:
        logging.error(f"Ошибка в handle_admin_find_users: {e}")
        await message.reply(f"Ошибка при поиске пользователей: {e}")

@router.message(commands=["admin_user_info"])
async def handle_admin_user_info(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("Нет доступа. Только для администраторов.")
        return
    args = message.get_args() if hasattr(message, 'get_args') else message.text[len("/admin_user_info"):].strip()
    user_id = None
    for part in args.split():
        if part.startswith("user_id="):
            try:
                user_id = int(part.split("=", 1)[1])
            except Exception:
                pass
    if not user_id:
        await message.reply("Укажите user_id: /admin_user_info user_id=123456")
        return
    try:
        async with SessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                await message.reply(f"Пользователь с id={user_id} не найден.")
                return
            context = user.context or {}
            summary = context.get('summary')
            gender = context.get('gender')
            info = (
                f"ID: {user.id}\n"
                f"Username: @{user.username}\n"
                f"Имя: {user.first_name or ''} {user.last_name or ''}\n"
                f"is_active: {user.is_active}\n"
                f"Gender: {gender}\n"
                f"Summary: {summary or '-'}\n"
            )
            ctx_str = str(context)
            if len(ctx_str) < 1500:
                info += f"Context: {ctx_str}\n"
            else:
                info += f"Context: слишком длинный ({len(ctx_str)} символов)\n"
            await message.reply(info)
    except Exception as e:
        logging.error(f"Ошибка в handle_admin_user_info: {e}")
        await message.reply(f"Ошибка при получении информации: {e}")

@router.message()
async def handle_message(message: types.Message):
    try:
        summary = await generate_summary(message.text)
        async with SessionLocal() as session:
            # Получаем или создаём пользователя
            user = await session.get(User, message.from_user.id)
            if not user:
                user = User(
                    id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                    is_active=True,
                    context={}
                )
                session.add(user)
            # Обновляем context: summary и relove_context
            user.context = user.context or {}
            user.context['last_message'] = message.text
            user.context['summary'] = summary
            # Можно обновлять relove_context через get_profile_summary или отдельную функцию
            profile_summary = await get_profile_summary(message.from_user.id, session)
            user.context['relove_context'] = profile_summary
            await session.commit()
            relove_context = user.context.get("relove_context")
        # Генерируем персонализированный ответ с учетом контекста
        if relove_context:
            prompt = (
                f"Контекст пользователя: {relove_context}\n"
                f"Новое сообщение пользователя: {message.text}\n"
                f"Дай персонализированную обратную связь для пробуждения и развития в потоке reLove."
            )
        else:
            prompt = (
                f"Профиль пользователя (summary): {summary}\n"
                f"Новое сообщение пользователя: {message.text}\n"
                f"Дай персонализированную обратную связь для пробуждения и развития в потоке reLove."
            )
        feedback = await generate_rag_answer(context="", question=prompt)
        await message.answer(feedback)
    except Exception as e:
        logging.error(f"Ошибка в handle_message: {e}")
        await message.answer("Произошла ошибка при обработке сообщения. Попробуйте позже.")

@router.message(commands=["similar"])
async def handle_similar(message: types.Message):
    try:
        args = message.get_args().strip()
        top_k = 5
        if args.isdigit():
            top_k = int(args)
        async with SessionLocal() as session:
            profile_summary = await get_profile_summary(message.from_user.id, session)
        if not profile_summary:
            await message.answer("Ваш профиль ещё не проанализирован. Напишите несколько сообщений для формирования профиля.")
            return
        query_embedding = await get_text_embedding(profile_summary)
        hits = search_similar_users(query_embedding, top_k=top_k)
        if not hits:
            await message.answer("Похожие пользователи не найдены.")
            return
        response = "Похожие пользователи:\n"
        for hit in hits:
            user_id = hit.id
            username = hit.payload.get("username") if hit.payload else None
            hero_stage = hit.payload.get("hero_path_stage") if hit.payload else None
            response += f"ID: {user_id} | username: {username or '-'} | этап: {hero_stage or '-'}\n"
        await message.answer(response)
    except Exception as e:
        logging.error(f"Ошибка в /similar: {e}")
        await message.answer("Ошибка при поиске похожих пользователей. Попробуйте позже.")