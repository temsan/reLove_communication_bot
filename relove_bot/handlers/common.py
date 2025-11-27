import logging
import asyncio
from aiogram import Router, types
from aiogram.types import CallbackQuery
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
from relove_bot.services.prompts import MESSAGE_SUMMARY_PROMPT, NATASHA_PROVOCATIVE_PROMPT

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
from relove_bot.services.prompts import NATASHA_PROVOCATIVE_PROMPT

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
    """Приветствие с информацией о событиях и возможностях"""
    from relove_bot.keyboards.main_menu import get_main_menu_keyboard
    from relove_bot.services.session_service import SessionService
    from relove_bot.constants.welcome_message import WELCOME_MESSAGE
    
    tg_user = message.from_user
    db_user = await get_or_create_user(session, tg_user)

    if not db_user:
        logger.error(f"Failed to get or create user for ID {tg_user.id}")
        await message.answer("Произошла ошибка при обработке вашего профиля. Попробуйте позже.")
        return
    
    user_name = db_user.first_name or "друг"
    logger.info(f"User {user_name} (ID: {db_user.id}) started the bot.")
    
    # Создаем inline клавиатуру для приветственного сообщения
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from relove_bot.constants.welcome_message import WELCOME_KEYBOARD_BUTTONS
    
    # Создаем кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 События Сообщества", callback_data="events")],
        [InlineKeyboardButton(text="👥 Проводники reLove", callback_data="guides")],
        [InlineKeyboardButton(text="💰 Реферальная программа", callback_data="referral_program")],
        [
            InlineKeyboardButton(text="🆘 Помощь", callback_data="help"),
            InlineKeyboardButton(text="❓ FAQ", callback_data="faq")
        ]
    ])
    
    # Отправляем приветственный пост с информацией о событиях
    try:
        await message.answer(
            WELCOME_MESSAGE,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error sending welcome message: {e}")
        await message.answer(
            "Добро пожаловать в reLove бот! 🔥\n\n"
            "Выбери действие из меню ниже.",
            reply_markup=keyboard
        )
    
    # Отправляем основное меню с кнопками
    await message.answer(
        "💡 Выбери действие или просто напиши мне:",
        reply_markup=get_main_menu_keyboard()
    )

@router.message(Command(commands=["diagnostic"]))
async def handle_diagnostic_command(message: types.Message, session: AsyncSession):
    """Команда для запуска диагностики"""
    from relove_bot.handlers.flexible_diagnostic import start_flexible_diagnostic
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=f"{message.chat.id}:{message.from_user.id}")
    
    await start_flexible_diagnostic(message, state, session)

@router.message(Command(commands=["streams"]))
async def handle_streams_command(message: types.Message):
    """Команда для показа потоков"""
    from relove_bot.keyboards.main_menu import get_streams_keyboard
    
    await message.answer(
        "🌀 <b>Потоки reLove</b>\n\n"
        "Выбери поток для подробной информации:",
        parse_mode="HTML",
        reply_markup=get_streams_keyboard()
    )

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
    """Оптимизированный обработчик сообщений с асинхронной обработкой"""
    user_id = message.from_user.id
    
    try:
        # 1. МГНОВЕННЫЙ ОТКЛИК - показываем "печатает..." и отправляем в фон
        try:
            await message.chat.do("typing")
        except Exception:
            pass  # Игнорируем ошибки при отправке статуса
        
        # 2. Запускаем обработку в фоне (не ждем результата)
        asyncio.create_task(
            _process_message_async(user_id, message)
        )
        
    except Exception as e:
        logging.error(f"Ошибка в handle_message: {e}", exc_info=True)


async def _process_message_async(user_id: int, message: types.Message):
    """Асинхронная обработка сообщения в фоне"""
    try:
        # Таймаут 30 сек на всю обработку
        async with asyncio.timeout(30):
            # 1. Получаем или создаём пользователя (быстро из кэша или БД)
            user_data = await _get_or_create_user_cached(user_id, message.from_user)
            
            if not user_data:
                await message.answer("❌ Ошибка при обработке профиля.")
                return
            
            # 2. Генерируем ответ (основная работа)
            feedback = await _generate_response(user_id, message.text, user_data)
            
            # 3. Отправляем ответ
            if feedback:
                await message.answer(feedback)
                
                # 4. Добавляем реакцию (не критично, если не получится)
                try:
                    await message.react([{"type": "emoji", "emoji": "👁"}])
                except Exception:
                    pass
            
            # 5. Обновляем профиль в фоне (не блокируем)
            asyncio.create_task(
                _update_user_profile_async(user_id, message.text)
            )
            
    except asyncio.TimeoutError:
        logging.warning(f"Таймаут обработки сообщения от {user_id}")
        try:
            await message.answer("⏱️ Обработка заняла слишком много времени. Попробуйте позже.")
        except Exception:
            pass
    except Exception as e:
        logging.error(f"Ошибка в _process_message_async: {e}", exc_info=True)
        try:
            await message.answer("❌ Произошла ошибка при обработке сообщения.")
        except Exception:
            pass


# Кэш пользователей в памяти (LRU)
_user_cache = {}
_cache_max_size = 1000

async def _get_or_create_user_cached(user_id: int, tg_user) -> dict:
    """Получает пользователя из кэша или БД"""
    # Проверяем кэш
    if user_id in _user_cache:
        return _user_cache[user_id]
    
    try:
        async with SessionLocal() as session:
            user = await session.get(User, user_id)
            
            if not user:
                # Создаем нового пользователя
                user = User(
                    id=user_id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    last_name=tg_user.last_name,
                    is_active=True,
                    markers={}
                )
                session.add(user)
                await session.commit()
                logging.info(f"Создан новый пользователь {user_id}")
            
            # Кэшируем данные
            user_data = {
                'id': user.id,
                'markers': user.markers or {},
                'profile': user.profile or ''
            }
            
            # Простая LRU: если кэш переполнен, удаляем старые записи
            if len(_user_cache) >= _cache_max_size:
                oldest_key = next(iter(_user_cache))
                del _user_cache[oldest_key]
            
            _user_cache[user_id] = user_data
            return user_data
            
    except Exception as e:
        logging.error(f"Ошибка при получении пользователя {user_id}: {e}")
        return None


async def _generate_response(user_id: int, text: str, user_data: dict) -> str:
    """Генерирует ответ с использованием LLM"""
    try:
        # Получаем контекст из кэша
        relove_context = user_data.get('markers', {}).get('relove_context', '')
        
        # Формируем промпт (минимальный размер для скорости)
        if relove_context:
            full_prompt = (
                f"{NATASHA_PROVOCATIVE_PROMPT}\n\n"
                f"Контекст: {relove_context[:500]}\n"  # Ограничиваем размер контекста
                f"Сообщение: {text[:200]}"  # Ограничиваем размер сообщения
            )
        else:
            full_prompt = (
                f"{NATASHA_PROVOCATIVE_PROMPT}\n\n"
                f"Сообщение: {text[:200]}"
            )
        
        # Генерируем ответ с таймаутом
        try:
            async with asyncio.timeout(20):  # 20 сек на LLM
                feedback = await llm_service.generate_text(
                    prompt=full_prompt,
                    max_tokens=300,  # Меньше токенов = быстрее
                    temperature=0.7  # Немного ниже для стабильности
                )
        except asyncio.TimeoutError:
            feedback = "Обработка заняла слишком много времени. Попробуйте позже."
        
        return feedback.strip() if feedback else None
        
    except Exception as e:
        logging.error(f"Ошибка при генерации ответа для {user_id}: {e}")
        return None


async def _update_user_profile_async(user_id: int, text: str):
    """Обновляет профиль пользователя в фоне (не блокирует основной поток)"""
    try:
        async with asyncio.timeout(10):  # 10 сек на обновление
            async with SessionLocal() as session:
                user = await session.get(User, user_id)
                if user:
                    user.markers = user.markers or {}
                    user.markers['last_message'] = text[:500]  # Ограничиваем размер
                    user.markers['last_update'] = str(datetime.now())
                    await session.commit()
                    
                    # Обновляем кэш
                    if user_id in _user_cache:
                        _user_cache[user_id]['markers'] = user.markers
                        
    except asyncio.TimeoutError:
        logging.debug(f"Таймаут обновления профиля {user_id}")
    except Exception as e:
        logging.debug(f"Ошибка при обновлении профиля {user_id}: {e}")

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
        try:
            query_embedding = await get_text_embedding(profile_summary)
            hits = search_similar_users(query_embedding, top_k=top_k)
            if not hits:
                await message.answer(
                    "Похожие пользователи не найдены. "
                    "Убедитесь, что Qdrant запущен (docker run -p 6333:6333 qdrant/qdrant)"
                )
                return
        except Exception as e:
            logging.error(f"Ошибка при получении эмбеддинга или поиске: {e}")
            await message.answer(
                "Ошибка при поиске похожих пользователей. "
                "Убедитесь, что Qdrant запущен и настроен."
            )
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
    """Справка по боту"""
    from relove_bot.keyboards.main_menu import get_main_menu_keyboard
    
    user_name = message.from_user.full_name
    user_id = message.from_user.id
    logger.info(f"User {user_name} (ID: {user_id}) requested help.")
    
    help_text = (
        "💡 <b>Что я умею:</b>\n\n"
        "🔥 <b>Сессия с Наташей</b>\n"
        "Провокативная терапия в стиле Наташи Волкош. "
        "Вскрываем паттерны, работаем с корнем, идём к трансформации.\n\n"
        "🎯 <b>Диагностика</b>\n"
        "Гибкая диагностика через диалог. Определяем твой этап пути героя "
        "и даём рекомендации.\n\n"
        "🌀 <b>Потоки reLove</b>\n"
        "Узнай о доступных потоках: Путь Героя, Прошлые Жизни, "
        "Открытие Сердца, Трансформация Тени, Пробуждение.\n\n"
        "📊 <b>Мой профиль</b>\n"
        "Смотри свой метафизический профиль, путь героя и историю сессий.\n\n"
        "💡 <b>Анализ готовности</b>\n"
        "Анализируем твою готовность к потокам на основе истории общения.\n\n"
        "Просто выбери действие из меню или напиши мне — я отвечу! 💬"
    )
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


# Обработчики кнопок главного меню
@router.message(lambda message: message.text == "🔥 Сессия с Наташей")
async def menu_natasha_session(message: types.Message, session: AsyncSession):
    """Обработчик кнопки 'Сессия с Наташей'"""
    from relove_bot.handlers.provocative_natasha import start_provocative_session
    from aiogram.fsm.context import FSMContext
    
    # Получаем FSM context
    from aiogram.fsm.storage.memory import MemoryStorage
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=f"{message.chat.id}:{message.from_user.id}")
    
    await start_provocative_session(message, state, session)


@router.message(lambda message: message.text == "🎯 Диагностика")
async def menu_diagnostic(message: types.Message, session: AsyncSession):
    """Обработчик кнопки 'Диагностика'"""
    from relove_bot.keyboards.main_menu import get_diagnostic_keyboard
    
    await message.answer(
        "🎯 <b>Гибкая диагностика</b>\n\n"
        "Это свободный диалог, где я задаю вопросы, адаптируясь под твои ответы.\n\n"
        "В конце определим твой этап пути героя и дадим рекомендации.\n\n"
        "Обычно занимает 5-10 минут.",
        parse_mode="HTML",
        reply_markup=get_diagnostic_keyboard()
    )


@router.message(lambda message: message.text == "🌀 Потоки reLove")
async def menu_streams(message: types.Message):
    """Обработчик кнопки 'Потоки reLove'"""
    from relove_bot.keyboards.main_menu import get_streams_keyboard
    
    await message.answer(
        "🌀 <b>Потоки reLove</b>\n\n"
        "Выбери поток, чтобы узнать подробности:",
        parse_mode="HTML",
        reply_markup=get_streams_keyboard()
    )


@router.message(lambda message: message.text == "📊 Мой профиль")
async def menu_profile(message: types.Message, session: AsyncSession):
    """Обработчик кнопки 'Мой профиль'"""
    from relove_bot.keyboards.main_menu import get_profile_keyboard
    from relove_bot.db.repository import UserRepository
    
    user_id = message.from_user.id
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    
    if not user:
        await message.answer("Профиль не найден. Начни с /start")
        return
    
    profile_text = f"📊 <b>Твой профиль</b>\n\n"
    profile_text += f"👤 {user.first_name or 'Без имени'}\n"
    
    if user.gender:
        profile_text += f"⚧ {user.gender.value}\n"
    
    if user.last_journey_stage:
        profile_text += f"🎯 Этап пути: {user.last_journey_stage.value}\n"
    
    if user.streams:
        profile_text += f"🌀 Потоки: {', '.join(user.streams)}\n"
    
    profile_text += f"\nВыбери, что хочешь посмотреть:"
    
    await message.answer(
        profile_text,
        parse_mode="HTML",
        reply_markup=get_profile_keyboard()
    )


@router.message(lambda message: message.text == "💡 Анализ готовности")
async def menu_analyze_readiness(message: types.Message, session: AsyncSession):
    """Обработчик кнопки 'Анализ готовности'"""
    from relove_bot.handlers.provocative_natasha import analyze_user_readiness
    
    await analyze_user_readiness(message, session)


@router.message(lambda message: message.text == "❓ Помощь")
async def menu_help(message: types.Message):
    """Обработчик кнопки 'Помощь'"""
    await handle_help(message)


# Новые обработчики для кнопок приветственного меню
@router.callback_query(lambda c: c.data == "events")
async def callback_events(callback: CallbackQuery):
    """Обработчик кнопки 'События Сообщества'"""
    events_text = (
        "📅 <b>События Сообщества reLove</b>\n\n"
        "<b>Ближайшие события:</b>\n\n"
        "🔻 <b>Запись Полнолуние 7.10. Разрыв кармических связей</b>\n"
        "Ритуал с Наташей Волкош\n\n"
        "Инструкция для оплаты:\n"
        "«События сообщества» ▶️ «Практики и медитации» ▶️ ПОЛНОЛУНИЕ. Разрыв кармических связей.\n\n"
        "🔻 <b>Запись ритуала Равности Любви с Наташей Волкош</b>\n"
        "Доступна сейчас.\n\n"
        "Инструкция для оплаты:\n"
        "«События сообщества» ▶️ «Практики и медитации» ▶️ Ритуал Равности Любви\n\n"
        "🔻 <b>Запись ритуала KALI 909 с Наташей Волкош, только для женщин.</b>\n"
        "Доступна сейчас.\n\n"
        "Инструкция для оплаты:\n"
        "«События сообщества» ▶️ «Практики и медитации» ▶️ KALI 909"
    )
    await callback.message.answer(events_text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "guides")
async def callback_guides(callback: CallbackQuery):
    """Обработчик кнопки 'Проводники reLove'"""
    guides_text = (
        "👥 <b>Проводники reLove</b>\n\n"
        "Наши проводники — опытные специалисты, которые помогут тебе на пути трансформации:\n\n"
        "🔥 <b>Наташа Волкош</b>\n"
        "Основатель reLove, провокативный терапевт, автор методики пробуждения через честный разговор.\n\n"
        "💫 <b>Команда проводников</b>\n"
        "Психологи, коучи и наставники, прошедшие путь героя и готовые поддержать тебя.\n\n"
        "📞 <b>Как получить поддержку:</b>\n"
        "Выбери диагностику в меню, и мы подберем подходящего проводника для твоего пути."
    )
    await callback.message.answer(guides_text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "referral_program")
async def callback_referral(callback: CallbackQuery):
    """Обработчик кнопки 'Реферальная программа'"""
    referral_text = (
        "💰 <b>Реферальная программа reLove</b>\n\n"
        "Приглашай друзей в reLove и получай бонусы!\n\n"
        "🎁 <b>Что ты получаешь:</b>\n"
        "• Скидки на участие в потоках\n"
        "• Бонусы за каждого приглашенного\n"
        "• Доступ к эксклюзивным материалам\n\n"
        "🔗 <b>Твоя реферальная ссылка:</b>\n"
        f"https://t.me/Relove_love_bot?start={callback.from_user.id}\n\n"
        "Делись ссылкой с друзьями и помогай им начать путь трансформации!"
    )
    await callback.message.answer(referral_text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "help")
async def callback_help(callback: CallbackQuery):
    """Обработчик кнопки 'Помощь'"""
    help_text = (
        "🆘 <b>Помощь</b>\n\n"
        "💡 <b>Что я умею:</b>\n\n"
        "🎯 <b>Диагностика</b> — определи свой психотип и этап пути героя\n\n"
        "💬 <b>Гибкая диагностика</b> — свободный диалог с адаптивными вопросами\n\n"
        "🔥 <b>Сессия с Наташей</b> — провокативная терапия для пробуждения\n\n"
        "🌀 <b>Потоки reLove</b> — узнай о мужском, женском и смешанном потоках\n\n"
        "📊 <b>Мой профиль</b> — посмотри свой психологический анализ\n\n"
        "💡 <b>Анализ готовности</b> — проверь готовность к потокам\n\n"
        "Просто выбери действие из меню или напиши мне — я отвечу! 💬"
    )
    await callback.message.answer(help_text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "faq")
async def callback_faq(callback: CallbackQuery):
    """Обработчик кнопки 'FAQ'"""
    faq_text = (
        "❓ <b>Часто задаваемые вопросы (FAQ)</b>\n\n"
        "<b>Q: Что такое reLove?</b>\n"
        "A: reLove — это сообщество трансформации через путь героя, основанное Наташей Волкош.\n\n"
        "<b>Q: Как пройти диагностику?</b>\n"
        "A: Выбери «Диагностика» в меню или напиши /diagnostic\n\n"
        "<b>Q: Что такое потоки reLove?</b>\n"
        "A: Это программы трансформации: мужской, женский и смешанный потоки. Выбери «Потоки reLove» в меню.\n\n"
        "<b>Q: Как получить доступ к подписке?</b>\n"
        "A: Оформи подписку в боте @reLove_subscription_bot\n\n"
        "<b>Q: Нужна помощь?</b>\n"
        "A: Напиши мне или выбери «Помощь» в меню!"
    )
    await callback.message.answer(faq_text, parse_mode="HTML")
    await callback.answer()


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


# Обработчики callback-кнопок
from aiogram.types import CallbackQuery

@router.callback_query(lambda c: c.data == "back_to_menu")
async def callback_back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    from relove_bot.keyboards.main_menu import get_main_menu_keyboard
    
    await callback.message.edit_text(
        "Главное меню 🏠\n\nВыбери действие:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "start_diagnostic")
async def callback_start_diagnostic(callback: CallbackQuery, session: AsyncSession):
    """Начать диагностику"""
    from relove_bot.handlers.flexible_diagnostic import start_flexible_diagnostic
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    
    # Отправляем текст выбора
    await callback.message.answer("🎯 Диагностика")
    
    # Удаляем сообщение с кнопками
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    
    # Создаём message из callback
    message = callback.message
    message.from_user = callback.from_user
    
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=f"{message.chat.id}:{callback.from_user.id}")
    
    await callback.answer()
    await start_flexible_diagnostic(message, state, session)


@router.callback_query(lambda c: c.data == "diagnostic_info")
async def callback_diagnostic_info(callback: CallbackQuery):
    """Информация о диагностике"""
    from relove_bot.keyboards.main_menu import get_diagnostic_keyboard
    
    info_text = (
        "🎯 <b>О диагностике</b>\n\n"
        "Это не опросник с фиксированными вопросами.\n\n"
        "Я буду задавать вопросы, адаптируясь под твои ответы. "
        "Мы поговорим о том, что важно для тебя сейчас.\n\n"
        "В конце я определю твой этап пути героя по Кэмпбеллу "
        "и дам конкретные рекомендации.\n\n"
        "Готов(а) начать?"
    )
    
    await callback.message.edit_text(
        info_text,
        parse_mode="HTML",
        reply_markup=get_diagnostic_keyboard()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("stream_"))
async def callback_stream_info(callback: CallbackQuery):
    """Показать информацию о потоке"""
    from relove_bot.keyboards.main_menu import get_streams_keyboard
    
    stream_id = callback.data.replace("stream_", "")
    
    streams_info = {
        "hero_path": {
            "name": "🎯 Путь Героя",
            "description": "Трансформация через прохождение внутреннего пути по 12 этапам Кэмпбелла.",
            "what_to_expect": "Работа с вызовом, отказом, встречей с наставником, пересечением порога. "
                             "Проходишь испытания, получаешь награду, возвращаешься с эликсиром.",
            "duration": "3 месяца",
            "format": "Еженедельные сессии + практики"
        },
        "past_lives": {
            "name": "🌌 Прошлые Жизни",
            "description": "Работа с планетарными историями и кармическими паттернами.",
            "what_to_expect": "Вскрытие памяти прошлых воплощений, исцеление планетарных травм, "
                             "освобождение от кармических долгов.",
            "duration": "2 месяца",
            "format": "Глубинные сессии + медитации"
        },
        "heart_opening": {
            "name": "❤️ Открытие Сердца",
            "description": "Работа с любовью, принятием и открытостью.",
            "what_to_expect": "Снятие защит, работа со страхом любви, раскрытие сердца, "
                             "принятие себя и других.",
            "duration": "2 месяца",
            "format": "Практики открытости + групповые сессии"
        },
        "shadow_work": {
            "name": "🌑 Трансформация Тени",
            "description": "Интеграция теневых частей личности.",
            "what_to_expect": "Принятие тьмы, работа с подавленными частями, баланс света и тьмы, "
                             "интеграция отвергнутого.",
            "duration": "3 месяца",
            "format": "Индивидуальная работа + практики"
        },
        "awakening": {
            "name": "✨ Пробуждение",
            "description": "Выход из матрицы обыденности.",
            "what_to_expect": "Осознание иллюзий, пробуждение к реальности, выход за пределы, "
                             "трансформация восприятия.",
            "duration": "4 месяца",
            "format": "Интенсивы + практики осознанности"
        }
    }
    
    stream = streams_info.get(stream_id)
    if not stream:
        await callback.answer("Поток не найден")
        return
    
    stream_text = (
        f"{stream['name']}\n\n"
        f"<b>Описание:</b>\n{stream['description']}\n\n"
        f"<b>Что тебя ждёт:</b>\n{stream['what_to_expect']}\n\n"
        f"<b>Длительность:</b> {stream['duration']}\n"
        f"<b>Формат:</b> {stream['format']}\n\n"
        "Это не лёгкий путь. Готов(а) к работе?\n\n"
        "Для регистрации свяжись с @NatashaVolkosh"
    )
    
    # Отправляем текст выбора потока
    await callback.message.answer(f"{stream['name']}")
    
    # Удаляем сообщение с кнопками выбора потока
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    
    # Отправляем информацию о потоке без кнопок
    await callback.message.answer(
        stream_text,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "show_streams")
async def callback_show_streams(callback: CallbackQuery):
    """Показать потоки"""
    from relove_bot.keyboards.main_menu import get_streams_keyboard
    
    await callback.message.edit_text(
        "🌀 <b>Потоки reLove</b>\n\n"
        "Выбери поток, чтобы узнать подробности:",
        parse_mode="HTML",
        reply_markup=get_streams_keyboard()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "metaphysical_profile")
async def callback_metaphysical_profile(callback: CallbackQuery, session: AsyncSession):
    """Показать метафизический профиль"""
    from relove_bot.handlers.provocative_natasha import show_metaphysical_profile
    
    # Создаём message из callback
    message = callback.message
    message.from_user = callback.from_user
    
    await callback.answer()
    await show_metaphysical_profile(message, session)


@router.callback_query(lambda c: c.data == "my_journey")
async def callback_my_journey(callback: CallbackQuery, session: AsyncSession):
    """Показать путь героя"""
    from relove_bot.db.repository import UserRepository
    from relove_bot.keyboards.main_menu import get_profile_keyboard
    
    user_id = callback.from_user.id
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    
    if not user or not user.last_journey_stage:
        await callback.message.edit_text(
            "🎯 <b>Твой путь героя</b>\n\n"
            "Этап пути ещё не определён.\n\n"
            "Пройди диагностику или начни сессию с Наташей, "
            "чтобы определить свой этап.",
            parse_mode="HTML",
            reply_markup=get_profile_keyboard()
        )
        await callback.answer()
        return
    
    journey_text = (
        f"🎯 <b>Твой путь героя</b>\n\n"
        f"Текущий этап: <b>{user.last_journey_stage.value}</b>\n\n"
    )
    
    # Описания этапов
    stage_descriptions = {
        "Обычный мир": "Ты в привычной реальности, но чувствуешь, что что-то не так.",
        "Зов к приключению": "Жизнь зовёт тебя к изменениям. Ты слышишь этот зов?",
        "Отказ от призыва": "Страх и сомнения удерживают тебя. Это нормально.",
        "Встреча с наставником": "Ты встретил того, кто поможет тебе начать путь.",
        "Пересечение порога": "Ты делаешь первый шаг в неизвестное.",
        "Испытания, союзники, враги": "Ты проходишь испытания, учишься различать.",
        "Приближение к сокровенной пещере": "Ты приближаешься к главному испытанию.",
        "Испытание": "Ты встречаешься со своим главным страхом.",
        "Награда": "Ты получил дар — новое понимание себя.",
        "Дорога назад": "Ты возвращаешься в мир, но уже другим.",
        "Воскресение": "Финальная трансформация. Ты умираешь и рождаешься заново.",
        "Возвращение с эликсиром": "Ты вернулся с даром для мира."
    }
    
    description = stage_descriptions.get(user.last_journey_stage.value, "")
    if description:
        journey_text += f"{description}\n\n"
    
    journey_text += "Продолжай работу, чтобы двигаться дальше по пути."
    
    await callback.message.edit_text(
        journey_text,
        parse_mode="HTML",
        reply_markup=get_profile_keyboard()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "session_history")
async def callback_session_history(callback: CallbackQuery, session: AsyncSession):
    """Показать историю сессий"""
    from relove_bot.services.session_service import SessionService
    from relove_bot.keyboards.main_menu import get_profile_keyboard
    
    user_id = callback.from_user.id
    session_service = SessionService(session)
    
    # Получаем последние 5 сессий
    sessions = await session_service.repository.get_user_sessions(
        user_id=user_id,
        limit=5,
        include_inactive=True
    )
    
    if not sessions:
        await callback.message.edit_text(
            "📊 <b>История сессий</b>\n\n"
            "У тебя пока нет завершённых сессий.\n\n"
            "Начни сессию с Наташей, чтобы создать историю.",
            parse_mode="HTML",
            reply_markup=get_profile_keyboard()
        )
        await callback.answer()
        return
    
    history_text = "📊 <b>История сессий</b>\n\n"
    
    for s in sessions:
        session_type_names = {
            "provocative": "🔥 Провокативная",
            "diagnostic": "🎯 Диагностика",
            "journey": "🎯 Путь героя"
        }
        
        type_name = session_type_names.get(s.session_type, s.session_type)
        status = "✅ Завершена" if not s.is_active else "⏳ Активна"
        date = s.created_at.strftime("%d.%m.%Y")
        
        history_text += f"{type_name} — {status}\n"
        history_text += f"Дата: {date}\n"
        history_text += f"Сообщений: {s.question_count or 0}\n\n"
    
    await callback.message.edit_text(
        history_text,
        parse_mode="HTML",
        reply_markup=get_profile_keyboard()
    )
    await callback.answer()


# Обработчики кнопок меню
@router.message(lambda message: message.text == "📊 Моя сессия")
async def handle_my_session_button(message: types.Message, session: AsyncSession):
    """Обработчик кнопки 'Моя сессия'"""
    try:
        from relove_bot.services.session_service import SessionService
        from relove_bot.services.ui_manager import UIManager
        
        user_id = message.from_user.id
        session_service = SessionService(session)
        ui_manager = UIManager()
        
        # Получаем активную сессию
        active_session = await session_service.repository.get_active_session(user_id, "provocative")
        
        if not active_session:
            await message.answer(
                "У тебя нет активной сессии.\n\n"
                "Начни с /natasha"
            )
            return
        
        # Получаем пользователя для этапа пути
        from relove_bot.db.models import User
        from sqlalchemy import select
        
        query = select(User).where(User.id == user_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        # Формируем сводку
        question_count = active_session.question_count or 0
        stage = user.last_journey_stage if user else None
        stage_text = stage.value if stage else "Не определён"
        
        # Прогресс индикатор
        progress_text = ""
        if stage and user:
            from relove_bot.services.journey_service import JourneyTrackingService
            journey_service = JourneyTrackingService(session)
            progress_list = await journey_service.get_journey_progress(user_id)
            
            completed = [p.current_stage.value for p in progress_list if p.current_stage != stage]
            progress_text = ui_manager.format_progress_indicator(stage, completed)
        
        response = f"""**📊 Твоя сессия**

**Вопросов задано:** {question_count}
**Текущий этап:** {stage_text}

{progress_text}

_Продолжить: просто напиши мне_
_Завершить: /end_session_
"""
        
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in my_session handler: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении информации о сессии.")


@router.message(lambda message: message.text == "🌌 Мой профиль")
async def handle_my_profile_button(message: types.Message, session: AsyncSession):
    """Обработчик кнопки 'Мой профиль'"""
    try:
        from relove_bot.db.models import User
        from sqlalchemy import select
        
        user_id = message.from_user.id
        
        # Получаем пользователя
        query = select(User).where(User.id == user_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Профиль не найден.")
            return
        
        # Формируем профиль
        profile_text = f"""**🌌 Твой профиль**

**Имя:** {user.first_name or 'Не указано'}
**Username:** @{user.username or 'Не указано'}
**Пол:** {user.gender.value if user.gender else 'Не определён'}
"""
        
        # Добавляем метафизический профиль если есть
        if user.metaphysical_profile:
            profile = user.metaphysical_profile
            profile_text += f"""
**🔮 Метафизический профиль:**

**Планета:** {profile.get('planetary_type', 'unknown').upper()}
{profile.get('planetary_description', '')}

**Кармический паттерн:** {profile.get('karmic_pattern', 'unknown').upper()}

**Баланс света/тьмы:**
{profile.get('balance', 'Не определён')}
"""
        
        # Добавляем этап пути
        if user.last_journey_stage:
            profile_text += f"\n**🗺 Текущий этап пути:** {user.last_journey_stage.value}"
        
        # Добавляем потоки
        if user.streams:
            streams_text = ", ".join(user.streams)
            profile_text += f"\n\n**🌀 Потоки:** {streams_text}"
        
        await message.answer(profile_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in my_profile handler: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении профиля.")


@router.message(lambda message: message.text == "🔥 Потоки")
async def handle_streams_button(message: types.Message, session: AsyncSession):
    """Обработчик кнопки 'Потоки'"""
    try:
        from relove_bot.keyboards.psychological import get_stream_selection_keyboard
        
        await message.answer(
            "**Потоки reLove** 🌀\n\n"
            "1. **Путь Героя** — внутренняя трансформация\n"
            "2. **Прошлые Жизни** — работа с кармой\n"
            "3. **Открытие Сердца** — принятие любви\n"
            "4. **Трансформация Тени** — интеграция тьмы\n"
            "5. **Пробуждение** — выход из матрицы\n\n"
            "Выбери поток:",
            reply_markup=get_stream_selection_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in streams handler: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении потоков.")


@router.message(lambda message: message.text == "⏸ Пауза")
async def handle_pause_button(message: types.Message, session: AsyncSession):
    """Обработчик кнопки 'Пауза'"""
    try:
        from relove_bot.db.models import User
        from sqlalchemy import select
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        user_id = message.from_user.id
        
        # Получаем пользователя
        query = select(User).where(User.id == user_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Пользователь не найден.")
            return
        
        # Устанавливаем флаг паузы
        if not user.markers:
            user.markers = {}
        
        user.markers['proactive_paused'] = True
        await session.commit()
        
        # Отменяем все запланированные триггеры
        from relove_bot.db.models import ProactiveTrigger
        from sqlalchemy import update
        
        await session.execute(
            update(ProactiveTrigger)
            .where(ProactiveTrigger.user_id == user_id)
            .where(ProactiveTrigger.executed == False)
            .values(executed=True, error_message="Cancelled by user pause")
        )
        await session.commit()
        
        # Кнопка возобновления
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="▶️ Продолжить", callback_data="resume_proactive")]
            ]
        )
        
        await message.answer(
            "⏸ **Проактивные сообщения приостановлены**\n\n"
            "Я не буду отправлять тебе напоминания и проактивные сообщения.\n"
            "Ты можешь продолжить диалог в любое время.\n\n"
            "Чтобы возобновить проактивность, нажми кнопку ниже.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in pause handler: {e}", exc_info=True)
        await message.answer("Произошла ошибка при установке паузы.")


@router.callback_query(lambda c: c.data == "resume_proactive")
async def handle_resume_callback(callback: types.CallbackQuery, session: AsyncSession):
    """Обработчик кнопки 'Продолжить'"""
    try:
        from relove_bot.db.models import User
        from sqlalchemy import select
        
        user_id = callback.from_user.id
        
        # Получаем пользователя
        query = select(User).where(User.id == user_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Пользователь не найден.")
            return
        
        # Снимаем флаг паузы
        if user.markers and 'proactive_paused' in user.markers:
            user.markers['proactive_paused'] = False
            await session.commit()
        
        # Напоминаем контекст
        from relove_bot.services.session_service import SessionService
        
        session_service = SessionService(session)
        active_session = await session_service.repository.get_active_session(user_id, "provocative")
        
        context_text = ""
        if active_session and active_session.conversation_history:
            last_messages = active_session.conversation_history[-2:]
            context_text = "\n\n**Последние сообщения:**\n"
            for msg in last_messages:
                role = "Наташа" if msg['role'] == 'assistant' else "Ты"
                context_text += f"{role}: {msg['content'][:100]}...\n"
        
        await callback.message.edit_text(
            f"▶️ **Проактивность возобновлена**\n\n"
            f"Я снова буду отправлять тебе напоминания и проактивные сообщения.{context_text}\n\n"
            f"Продолжим?",
            parse_mode="Markdown"
        )
        
        await callback.answer("Проактивность возобновлена")
        
    except Exception as e:
        logger.error(f"Error in resume handler: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при возобновлении.")
