"""
Обработчик для гибкой LLM-диагностики через свободный диалог.

Диагностика адаптируется под профиль пользователя и его ответы,
используя путь героя Кэмпбелла как метафорический каркас.
"""
import logging
from typing import Dict, Optional
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from relove_bot.services.llm_service import llm_service
from relove_bot.services.prompts import FLEXIBLE_DIAGNOSTIC_PROMPT
from relove_bot.db.models import User, DiagnosticResult, JourneyStageEnum
from relove_bot.db.repository import UserRepository

logger = logging.getLogger(__name__)
router = Router()

# Состояния для гибкой диагностики
class FlexibleDiagnosticStates(StatesGroup):
    in_diagnostic = State()
    completed = State()

# Хранилище активных диагностических сессий
active_diagnostic_sessions: Dict[int, Dict] = {}


def get_or_create_diagnostic_session(user_id: int) -> Dict:
    """Получает или создаёт сессию диагностики."""
    if user_id not in active_diagnostic_sessions:
        active_diagnostic_sessions[user_id] = {
            "conversation_history": [],
            "user_profile": None,
            "journey_stage": None,
            "message_count": 0
        }
    return active_diagnostic_sessions[user_id]


@router.message(Command("diagnostic"))
async def start_flexible_diagnostic(message: Message, state: FSMContext, session: AsyncSession):
    """
    Начинает гибкую диагностику через свободный диалог.
    
    Команда: /diagnostic
    """
    user_id = message.from_user.id
    
    # Получаем профиль пользователя
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    
    # Создаём сессию диагностики в БД
    session_service = SessionService(session)
    db_session = await session_service.get_or_create_session(
        user_id=user_id,
        session_type="diagnostic",
        state="in_diagnostic"
    )
    
    # Формируем контекст профиля для LLM
    profile_context = ""
    if user:
        if user.psychological_summary:
            profile_context += f"Психологический профиль:\n{user.psychological_summary}\n\n"
        if user.streams:
            profile_context += f"Потоки reLove: {', '.join(user.streams)}\n\n"
        if user.profile_summary:
            profile_context += f"Профиль: {user.profile_summary}\n\n"
    
    # Сохраняем контекст в session_data
    await session_service.update_session_data(
        db_session.id,
        session_data={"user_profile": profile_context}
    )
    
    # Генерируем первое сообщение от LLM
    system_prompt = FLEXIBLE_DIAGNOSTIC_PROMPT
    if profile_context:
        system_prompt += f"\n\nКОНТЕКСТ ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ:\n{profile_context}"
    
    try:
        first_message = await llm_service.analyze_text(
            "Начни диагностику. Поздоровайся и задай первый вопрос.",
            system_prompt=system_prompt,
            max_tokens=200
        )
        
        await session_service.add_message(
            db_session.id,
            "assistant",
            first_message or "Привет. Расскажи, что привело тебя сюда? Что сейчас важно?"
        )
        
        await message.answer(
            first_message or "Привет. Расскажи, что привело тебя сюда? Что сейчас важно?"
        )
        
        await state.set_state(FlexibleDiagnosticStates.in_diagnostic)
        
    except Exception as e:
        logger.error(f"Ошибка при старте диагностики: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при запуске диагностики. Попробуй позже."
        )


@router.message(FlexibleDiagnosticStates.in_diagnostic)
async def process_diagnostic_message(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обрабатывает сообщения пользователя в процессе диагностики.
    """
    user_id = message.from_user.id
    user_message = message.text
    
    if not user_message:
        await message.answer("Отправь текстовое сообщение, пожалуйста.")
        return
    
    # Получаем активную сессию из БД
    session_service = SessionService(session)
    db_session = await session_service.get_active_session(user_id, "diagnostic")
    
    if not db_session:
        await message.answer("Диагностическая сессия не найдена. Начни новую: /diagnostic")
        await state.clear()
        return
    
    # Добавляем сообщение пользователя
    await session_service.add_message(db_session.id, "user", user_message)
    
    # Получаем историю диалога из БД
    conversation_history = db_session.conversation_history or []
    
    # Формируем контекст диалога
    conversation_context = "\n".join([
        f"{'Диагност' if msg['role'] == 'assistant' else 'Человек'}: {msg['content']}"
        for msg in conversation_history[-10:]
    ])
    
    # Получаем user_profile из session_data
    user_profile = ""
    if db_session.session_data and "user_profile" in db_session.session_data:
        user_profile = db_session.session_data["user_profile"]
    
    # Формируем промпт
    system_prompt = FLEXIBLE_DIAGNOSTIC_PROMPT
    if user_profile:
        system_prompt += f"\n\nКОНТЕКСТ ПРОФИЛЯ:\n{user_profile}"
    
    prompt = f"""ИСТОРИЯ ДИАЛОГА:
{conversation_context}

НОВОЕ СООБЩЕНИЕ ЧЕЛОВЕКА:
{user_message}

ТВОЯ ЗАДАЧА:
Ответь на сообщение человека. Задай вопрос или дай инсайт, если видишь готовность.
После 3-5 обменов сообщениями предложи определить этап пути героя.

Если видишь готовность определить этап — дай инсайт в формате:
"Похоже, ты сейчас в [этап пути]. Это значит [объяснение]."
"""
    
    try:
        response = await llm_service.analyze_text(
            prompt,
            system_prompt=system_prompt,
            max_tokens=300
        )
        
        if not response:
            await message.answer("Попробуй ещё раз, я не понял.")
            return
        
        await session_service.add_message(db_session.id, "assistant", response)
        
        await message.answer(response)
        
        # Получаем обновлённую сессию для подсчёта сообщений
        updated_session = await session_service.repository.get_session_by_id(db_session.id)
        message_count = len(updated_session.conversation_history) if updated_session.conversation_history else 0
        
        # Если уже есть несколько обменов, предлагаем завершить диагностику
        if message_count >= 6:
            await message.answer(
                "\n\n💡 Хочешь завершить диагностику и получить резюме? Напиши /end_diagnostic"
            )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения диагностики: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуй ещё раз.")


@router.message(Command("end_diagnostic"))
async def end_diagnostic(message: Message, state: FSMContext, session: AsyncSession):
    """
    Завершает диагностику и сохраняет результаты.
    
    Команда: /end_diagnostic
    """
    user_id = message.from_user.id
    
    # Получаем активную сессию из БД
    session_service = SessionService(session)
    db_session = await session_service.get_active_session(user_id, "diagnostic")
    
    if not db_session:
        await message.answer("Активной диагностики нет. Начни с /diagnostic")
        await state.clear()
        return
    
    conversation_history = db_session.conversation_history or []
    
    # Формируем итоговый анализ
    conversation_text = "\n".join([
        f"{'Диагност' if msg['role'] == 'assistant' else 'Человек'}: {msg['content']}"
        for msg in conversation_history
    ])
    
    analysis_prompt = f"""
Проанализируй диагностический диалог и определи:

1. ЭТАП ПУТИ ГЕРОЯ (точное название из списка):
- Обычный мир
- Зов к приключению
- Отказ от призыва
- Встреча с наставником
- Пересечение порога
- Испытания, союзники, враги
- Приближение к сокровенной пещере
- Испытание
- Награда
- Дорога назад
- Воскресение
- Возвращение с эликсиром

2. КРАТКОЕ ОПИСАНИЕ текущего состояния

3. РЕКОМЕНДАЦИИ (2-3 конкретных шага)

ДИАЛОГ:
{conversation_text}

Ответь в формате:
ЭТАП: [название этапа]
СОСТОЯНИЕ: [описание]
ШАГИ: [1. шаг] [2. шаг] [3. шаг]
"""
    
    try:
        analysis = await llm_service.analyze_text(
            analysis_prompt,
            max_tokens=400
        )
        
        # Сохраняем результат в БД
        user_repo = UserRepository(session)
        user = await user_repo.get_user(user_id)
        
        if user:
            # Парсим этап из анализа
            journey_stage = None
            for stage in JourneyStageEnum:
                if stage.value in analysis:
                    journey_stage = stage
                    break
            
            # Создаём запись диагностики
            diagnostic_result = DiagnosticResult(
                user_id=user_id,
                journey_stage=journey_stage or JourneyStageEnum.ORDINARY_WORLD,
                description=analysis,
                answers={"conversation": conversation_history}
            )
            session.add(diagnostic_result)
            await session.commit()
        
        await message.answer(
            f"📊 **РЕЗУЛЬТАТЫ ДИАГНОСТИКИ**\n\n{analysis}\n\n"
            "Хочешь начать провокативную сессию с Наташей? /natasha\n"
            "Или узнать о потоках? /streams",
            parse_mode="Markdown"
        )
        
        # Завершаем сессию в БД
        await session_service.complete_session(db_session.id)
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при завершении диагностики: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при сохранении результатов. "
            "Но твой диалог сохранён, можешь вернуться позже."
        )

