import logging
from aiogram import Router, types
from aiogram.filters import Command, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from ..rag.llm import LLM
from ..db.session import SessionLocal
from ..db.models import UserActivityLog, User, GenderEnum
from datetime import datetime
from relove_bot.db.memory_index import user_memory_index
from relove_bot.services.llm_service import llm_service
from relove_bot.services.prompts import MESSAGE_SUMMARY_PROMPT

logger = logging.getLogger(__name__)
router = Router()

from ..rag.pipeline import get_profile_summary
from ..db.vector import search_similar_users
from ..utils.user_utils import select_users
import logging

# Список Telegram user_id админов
ADMIN_IDS = {123456789, 987654321}  # Замените на свои id

from relove_bot.utils.profile_utils import fill_all_profiles
from relove_bot.config import settings
import asyncio

async def get_or_create_user(session: AsyncSession, tg_user: types.User) -> User:
    """Gets a user from DB or creates/updates it."""
    # Пытаемся получить пользователя
    stmt = select(User).where(User.id == tg_user.id)
    result = await session.execute(stmt)
    db_user = result.scalar_one_or_none()

    if db_user:
        # Пользователь найден, проверяем, нужно ли обновить данные
        update_needed = False
        if db_user.username != tg_user.username:
            db_user.username = tg_user.username
            update_needed = True
        if db_user.first_name != tg_user.first_name:
            db_user.first_name = tg_user.first_name
            update_needed = True
        if db_user.last_name != tg_user.last_name:
            db_user.last_name = tg_user.last_name
            update_needed = True
        if not db_user.is_active: # Активируем, если был неактивен
             db_user.is_active = True
             update_needed = True

        if update_needed:
            logger.info(f"Updating user data for {tg_user.id}")
            await session.commit()
        # Обновляем last_seen неявно через onupdate=func.now() при любом SELECT/UPDATE,
        # но можно и явно: db_user.last_seen_date = datetime.datetime.now(datetime.timezone.utc)

        return db_user
    else:
        # Пользователь не найден, создаем нового
        logger.info(f"Creating new user for {tg_user.id}")
        new_user = User(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name or "", # first_name может быть None?
            last_name=tg_user.last_name,
            gender=GenderEnum.female,  # female по умолчанию
            is_active=True
            # registration_date установится по умолчанию
            # is_admin и другие поля по умолчанию
        )
        session.add(new_user)
        try:
            await session.commit()
            await session.refresh(new_user)
            return new_user
        except IntegrityError as e:
            logger.error(f"Integrity error creating user {tg_user.id}: {e}. Rolling back.")
            await session.rollback()
            # Попробуем снова получить пользователя, вдруг гонка состояний?
            result = await session.execute(select(User).where(User.id == tg_user.id))
            return result.scalar_one_or_none() # Может быть None, если ошибка не связана с гонкой
        except Exception as e:
            logger.exception(f"Error creating user {tg_user.id}: {e}. Rolling back.")
            await session.rollback()
            return None

@router.message(CommandStart())
async def handle_start(message: types.Message, session: AsyncSession):
    """Handles the /start command, creates or updates user in DB."""
    tg_user = message.from_user
    db_user = await get_or_create_user(session, tg_user)

    if db_user:
        user_name = db_user.first_name # Берем имя из БД
        logger.info(f"User {user_name} (ID: {db_user.id}) started the bot.")
        await message.answer(
            f"Привет, {user_name}! 👋\n\n" \
            f"Я Ассистент Релавы, готов помочь тебе с навигацией в нашем сообществе.\n"
            f"Используй команду /help, чтобы узнать больше о моих возможностях."
        )
    else:
         logger.error(f"Failed to get or create user for ID {tg_user.id}")
         await message.answer("Произошла ошибка при обработке вашего профиля. Попробуйте позже.")

@router.message(Command(commands=["admin_update_summaries"]))
async def handle_admin_update_summaries(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("Нет доступа. Только для администраторов.")
        return
    await message.reply("Обновление summary пользователей запущено!")
    # Запуск в фоне, чтобы не блокировать бота
    asyncio.create_task(fill_all_profiles(settings.channel_id))
    await message.reply("Обновление запущено в фоне. Результат будет доступен в логах.")

@router.message(Command(commands=["admin_find_users"]))
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

@router.message(Command(commands=["admin_user_info"]))
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
        # Сначала ищем в памяти
        user = user_memory_index.find_by_id(user_id) if user_memory_index else None
        if not user:
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
        llm = LLM()
        summary_struct = await llm.analyze_content(text=message.text)
        summary = summary_struct['summary']
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

@router.message(Command(commands=["similar"]))
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
            user_context = hit.payload.get("context") if hit.payload else None
            response += f"ID: {user_id} | username: {username or '-'} | контекст: {user_context or '-'}\n"
        await message.answer(response)
    except Exception as e:
        logging.error(f"Ошибка в /similar: {e}")
        await message.answer("Ошибка при поиске похожих пользователей. Попробуйте позже.")

@router.message(Command(commands=["help"]))
async def handle_help(message: types.Message):
    """Handles the /help command."""
    user_name = message.from_user.full_name
    user_id = message.from_user.id
    logger.info(f"User {user_name} (ID: {user_id}) requested help.")
    # TODO: Дополнить текст справки по мере добавления функционала
    help_text = (
        "ℹ️ **Справка по боту:**\\n\\n"
        "Я помогу тебе:\\n"
        "- Узнавать о предстоящих мероприятиях (потоках, ритуалах).\\n"
        "- Регистрироваться на мероприятия.\\n"
        "- (В будущем) Следить за твоим \\\"Путем Героя\\\" в сообществе.\\n\\n"
        "**Доступные команды:**\\n"
        "/start - Начать работу с ботом\\n"
        "/help - Показать это сообщение\\n"
        # "/events - Показать ближайшие мероприятия\\n"
        # "/my_registrations - Показать мои регистрации\\n"
    )
    await message.answer(help_text, parse_mode="HTML")

async def analyze_message(message: str) -> str:
    """
    Анализирует сообщение пользователя.
    
    Args:
        message: Текст сообщения
        
    Returns:
        str: Результат анализа или пустая строка в случае ошибки
    """
    try:
        result = await llm_service.analyze_text(
            text=message,
            system_prompt=MESSAGE_SUMMARY_PROMPT,
            max_tokens=64
        )
        
        if not result:
            return ''
            
        return result.strip()
        
    except Exception as e:
        logger.error(f"Ошибка при анализе сообщения: {e}", exc_info=True)
        return ''