"""
Обработчик для провокативного общения в стиле Наташи.

Этот модуль реализует провокативный стиль терапии,
вдохновлённый работой Наташи Волкош с участниками reLove.
"""
import logging
from typing import Dict, List, Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from relove_bot.services.session_service import SessionService
from relove_bot.db.repository import UserRepository

from relove_bot.services.llm_service import llm_service
from relove_bot.services.prompts import (
    NATASHA_PROVOCATIVE_PROMPT,
    STREAM_INVITATION_PROMPT
)
from relove_bot.services.metaphysical_service import metaphysical_service
from relove_bot.db.models import User
from relove_bot.keyboards.psychological import get_stream_selection_keyboard

logger = logging.getLogger(__name__)
router = Router()


class ProvocativeStates(StatesGroup):
    """Состояния для провокативной сессии."""
    waiting_for_response = State()
    deep_work = State()
    choosing_stream = State()


class ProvocativeSession:
    """
    Класс для управления провокативной сессией с пользователем.
    
    Реализует цепочки вопросов в стиле Наташи для вскрытия
    глубинных паттернов и подведения к трансформации.
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.conversation_history: List[Dict[str, str]] = []
        self.identified_patterns: List[str] = []
        self.core_issue: Optional[str] = None
        self.question_count = 0
        self.metaphysical_profile: Optional[Dict] = None
        self.core_trauma: Optional[Dict] = None
        
    def add_message(self, role: str, content: str):
        """Добавляет сообщение в историю диалога."""
        self.conversation_history.append({
            "role": role,
            "content": content
        })
        
    def get_conversation_context(self) -> str:
        """Формирует контекст из истории диалога."""
        context_parts = []
        for msg in self.conversation_history[-10:]:  # Последние 10 сообщений
            role = "Наташа" if msg["role"] == "assistant" else "Человек"
            context_parts.append(f"{role}: {msg['content']}")
        return "\n".join(context_parts)
    
    async def generate_provocative_response(self, user_message: str) -> str:
        """
        Генерирует провокативный ответ в стиле Наташи.
        LLM сама принимает решения об этапах и направлении работы.
        
        Args:
            user_message: Сообщение пользователя
            
        Returns:
            str: Ответ в стиле Наташи
        """
        self.add_message("user", user_message)
        self.question_count += 1
        
        # Формируем контекст диалога
        context = self.get_conversation_context()
        
        # Формируем промпт для LLM с полной историей
        prompt = f"""
{NATASHA_PROVOCATIVE_PROMPT}

ИСТОРИЯ ДИАЛОГА:
{context}

НОВОЕ СООБЩЕНИЕ ЧЕЛОВЕКА:
{user_message}

ТВОЯ ЗАДАЧА:
САМ реши, что нужно сейчас:
- Провокативный вопрос для углубления?
- Называние паттерна, который видишь?
- Работа с метафизическими концептами (планета, свет/тьма)?
- Вскрытие корня (обида, война, вампиризм)?
- Конкретная инструкция для трансформации?
- Предложение потока reLove?

Ответь в стиле Наташи — коротко, провокативно, точно.
Максимум 2-3 короткие фразы или 1-2 вопроса.
"""
        
        try:
            response = await llm_service.analyze_text(
                prompt=prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=200
            )
            
            self.add_message("assistant", response)
            
            # Если LLM упоминает потоки, помечаем это
            if any(stream in response.lower() for stream in ["путь героя", "прошлые жизни", "открытие сердца", "трансформация тени", "пробуждение"]):
                logger.info(f"LLM предложила поток для пользователя {self.user_id}")
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка при генерации провокативного ответа: {e}")
            return "..."
    
    async def analyze_readiness_for_stream(
        self,
        activity_history: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Анализирует готовность человека к конкретным потокам.
        
        Args:
            activity_history: Опциональная история активности из UserActivityLog
        
        Returns:
            dict: Словарь с рекомендованными потоками и причинами
        """
        context = self.get_conversation_context()
        
        # Если есть история активности, добавляем её к контексту
        history_context = ""
        if activity_history:
            history_context = f"\n\nИСТОРИЯ ОБЩЕНИЯ С БОТОМ (последние 30 дней):\n{activity_history}"
        
        prompt = f"""
{STREAM_INVITATION_PROMPT}

ТЕКУЩАЯ СЕССИЯ:
{context}
{history_context}

ЗАДАЧА:
Проанализируй ВСЕ доступные данные (текущая сессия + история общения) и определи:
1. К каким потокам человек готов (список)
2. Какие признаки готовности ты видишь (в текущей сессии И в истории)
3. Короткое провокативное приглашение на поток (1-2 предложения)

Ответь в формате:
ПОТОК: [название]
ПРИЗНАКИ: [что видишь]
ПРИГЛАШЕНИЕ: [короткое провокативное приглашение]
"""
        
        try:
            response = await llm_service.analyze_text(
                prompt=prompt,
                system_prompt=STREAM_INVITATION_PROMPT,
                max_tokens=400  # Увеличили для более детального анализа
            )
            
            # Парсим ответ
            return self._parse_stream_analysis(response)
            
        except Exception as e:
            logger.error(f"Ошибка при анализе готовности к потокам: {e}", exc_info=True)
            return {}
    
    def _parse_stream_analysis(self, response: str) -> Dict[str, any]:
        """Парсит ответ LLM о готовности к потокам."""
        result = {
            "recommended_streams": [],
            "reasons": [],
            "invitation": ""
        }
        
        lines = response.split('\n')
        current_stream = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("ПОТОК:"):
                current_stream = line.replace("ПОТОК:", "").strip()
                result["recommended_streams"].append(current_stream)
            elif line.startswith("ПРИЗНАКИ:"):
                reason = line.replace("ПРИЗНАКИ:", "").strip()
                result["reasons"].append(reason)
            elif line.startswith("ПРИГЛАШЕНИЕ:"):
                result["invitation"] = line.replace("ПРИГЛАШЕНИЕ:", "").strip()
        
        return result
    
    async def generate_session_summary(self) -> Dict[str, any]:
        """
        Генерирует итоговую сводку сессии.
        
        Returns:
            dict: Структурированная сводка с инсайтами, паттернами, корнем
        """
        if not self.conversation_history:
            return {}
        
        context = self.get_conversation_context()
        
        prompt = f"""
Проанализируй сессию и создай структурированную сводку.

ДИАЛОГ:
{context}

ЗАДАЧА:
Создай итоговый анализ в формате:

ИНСАЙТЫ:
[Ключевые прозрения, которые получил человек - 2-3 пункта]

ОБНАРУЖЕННЫЕ ПАТТЕРНЫ:
[Какие паттерны были вскрыты: вампиризм/обида/война/самообман/бегство]

КОРЕНЬ:
[Изначальная травма или обида, если удалось выявить]

ТРУДНОСТИ:
[С чем человек сталкивается, что мешает - 2-3 пункта]

ОБЩИЕ ТЕМЫ:
[Повторяющиеся темы в диалоге]

ПУТЬ ДАЛЬШЕ:
[Конкретные шаги для трансформации]

Будь конкретен и опирайся только на то, что было в диалоге.
"""
        
        try:
            response = await llm_service.analyze_text(
                prompt=prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=500
            )
            
            return self._parse_session_summary(response)
            
        except Exception as e:
            logger.error(f"Ошибка при генерации сводки сессии: {e}")
            return {}
    
    def _parse_session_summary(self, response: str) -> Dict[str, any]:
        """Парсит сводку сессии."""
        summary = {
            "insights": [],
            "patterns": [],
            "core": "",
            "difficulties": [],
            "themes": [],
            "next_steps": []
        }
        
        current_section = None
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("ИНСАЙТЫ:"):
                current_section = "insights"
            elif line.startswith("ОБНАРУЖЕННЫЕ ПАТТЕРНЫ:"):
                current_section = "patterns"
            elif line.startswith("КОРЕНЬ:"):
                current_section = "core"
            elif line.startswith("ТРУДНОСТИ:"):
                current_section = "difficulties"
            elif line.startswith("ОБЩИЕ ТЕМЫ:"):
                current_section = "themes"
            elif line.startswith("ПУТЬ ДАЛЬШЕ:"):
                current_section = "next_steps"
            elif line.startswith("-") or line.startswith("•"):
                content = line.lstrip("-• ").strip()
                if current_section and current_section != "core":
                    summary[current_section].append(content)
            elif current_section == "core" and not line.startswith(("ИНСАЙТЫ", "ОБНАРУЖЕННЫЕ", "ТРУДНОСТИ", "ОБЩИЕ", "ПУТЬ")):
                summary["core"] += line + " "
        
        # Очищаем корень
        summary["core"] = summary["core"].strip()
        
        return summary


# Глобальный словарь для быстрого доступа (кэш)
active_sessions_cache: Dict[int, ProvocativeSession] = {}


async def get_or_create_session(user_id: int, db_session: Optional[AsyncSession] = None) -> ProvocativeSession:
    """
    Получает или создаёт сессию для пользователя.
    
    Если db_session передан, создаёт сессию в БД и обёртывает её в ProvocativeSession.
    Если нет - использует кэш (устаревший способ, для обратной совместимости).
    """
    # Сначала проверяем кэш
    if user_id in active_sessions_cache:
        return active_sessions_cache[user_id]
    
    # Если есть БД сессия, работаем через неё
    if db_session:
        session_service = SessionService(db_session)
        db_user_session = await session_service.get_or_create_session(
            user_id=user_id,
            session_type="provocative",
            state="waiting_for_response"
        )
        
        # Создаём обёртку ProvocativeSession
        provocative_session = ProvocativeSession(user_id)
        provocative_session._db_session_id = db_user_session.id
        provocative_session._db_session = db_user_session
        provocative_session._session_service = session_service
        
        # Загружаем историю из БД
        if db_user_session.conversation_history:
            provocative_session.conversation_history = db_user_session.conversation_history
        provocative_session.question_count = db_user_session.question_count or 0
        provocative_session.identified_patterns = db_user_session.identified_patterns or []
        provocative_session.core_issue = db_user_session.core_issue
        provocative_session.metaphysical_profile = db_user_session.metaphysical_profile
        provocative_session.core_trauma = db_user_session.core_trauma
        
        active_sessions_cache[user_id] = provocative_session
        return provocative_session
    
    # Fallback на старый способ
    if user_id not in active_sessions_cache:
        active_sessions_cache[user_id] = ProvocativeSession(user_id)
    return active_sessions_cache[user_id]


@router.message(Command("natasha"))
async def start_provocative_session(message: Message, state: FSMContext, session: AsyncSession):
    """
    Начинает провокативную сессию в стиле Наташи.
    
    Команда: /natasha
    """
    user_id = message.from_user.id
    provocative_session = await get_or_create_session(user_id, db_session=session)
    
    # Очищаем историю для новой сессии
    provocative_session.conversation_history = []
    provocative_session.question_count = 0
    provocative_session.metaphysical_profile = None
    provocative_session.core_trauma = None
    
    await state.set_state(ProvocativeStates.waiting_for_response)
    
    # Первое сообщение в стиле Наташи - с запросом согласия
    greeting = "Привет. Ты здесь?"
    provocative_session.add_message("assistant", greeting)
    
    # Сохраняем в БД
    if hasattr(provocative_session, '_session_service') and provocative_session._db_session_id:
        await provocative_session._session_service.add_message(
            provocative_session._db_session_id,
            "assistant",
            greeting
        )
    
    await message.answer(
        f"{greeting}\n\n"
        "Вижу твое состояние. Готов(а) с этим поработать? Прямо сейчас.\n\n"
        "Я не утешитель. Я — Проводник. Буду вести тебя через неизбежный процесс:\n"
        "• Задавать неудобные вопросы\n"
        "• Вскрывать защиты и паттерны\n"
        "• Называть вещи своими именами\n"
        "• Доводить до точки принятия\n\n"
        "Это не будет комфортно. Но будет честно.\n"
        "Согласен(на)?"
    )


@router.message(ProvocativeStates.waiting_for_response)
async def handle_provocative_response(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обрабатывает ответы пользователя в провокативной сессии.
    """
    user_id = message.from_user.id
    provocative_session = await get_or_create_session(user_id, db_session=session)
    
    user_message = message.text
    
    # Генерируем провокативный ответ
    response = await provocative_session.generate_provocative_response(user_message)
    
    await message.answer(response)
    
    # Сохраняем в БД
    if hasattr(provocative_session, '_session_service') and provocative_session._db_session_id:
        await provocative_session._session_service.add_message(
            provocative_session._db_session_id,
            "user",
            user_message
        )
        await provocative_session._session_service.add_message(
            provocative_session._db_session_id,
            "assistant",
            response
        )
    
    # После 10+ вопросов предлагаем поток
    if provocative_session.question_count >= 10:
        analysis = await provocative_session.analyze_readiness_for_stream()
        
        if analysis.get("recommended_streams"):
            invitation = analysis.get("invitation", "")
            await message.answer(
                f"\n{invitation}\n\n"
                "Хочешь узнать больше о потоках?",
                reply_markup=get_stream_selection_keyboard()
            )
            await state.set_state(ProvocativeStates.choosing_stream)


@router.message(Command("end_session"))
async def end_provocative_session(message: Message, state: FSMContext, session: AsyncSession):
    """
    Завершает провокативную сессию с выводом итоговой сводки.
    
    Команда: /end_session
    """
    user_id = message.from_user.id
    
    # Получаем активную сессию
    provocative_session = await get_or_create_session(user_id, db_session=session)
    
    if provocative_session and provocative_session.question_count > 3:
        # Генерируем итоговую сводку сессии
        await message.answer("Формирую сводку сессии...")
        
        summary = await provocative_session.generate_session_summary()
        
        if summary:
                # Форматируем сводку
                summary_text = "**📊 ИТОГОВАЯ СВОДКА СЕССИИ**\n\n"
                
                if summary.get("insights"):
                    summary_text += "**💡 ИНСАЙТЫ:**\n"
                    for insight in summary["insights"]:
                        summary_text += f"• {insight}\n"
                    summary_text += "\n"
                
                if summary.get("patterns"):
                    summary_text += "**🔍 ОБНАРУЖЕННЫЕ ПАТТЕРНЫ:**\n"
                    for pattern in summary["patterns"]:
                        summary_text += f"• {pattern}\n"
                    summary_text += "\n"
                
                if summary.get("core"):
                    summary_text += f"**🎯 КОРЕНЬ:**\n{summary['core']}\n\n"
                
                if summary.get("difficulties"):
                    summary_text += "**⚠️ ТРУДНОСТИ:**\n"
                    for diff in summary["difficulties"]:
                        summary_text += f"• {diff}\n"
                    summary_text += "\n"
                
                if summary.get("themes"):
                    summary_text += "**📖 ОБЩИЕ ТЕМЫ:**\n"
                    for theme in summary["themes"]:
                        summary_text += f"• {theme}\n"
                    summary_text += "\n"
                
                if summary.get("next_steps"):
                    summary_text += "**🚀 ПУТЬ ДАЛЬШЕ:**\n"
                    for step in summary["next_steps"]:
                        summary_text += f"• {step}\n"
                
                await message.answer(summary_text, parse_mode="Markdown")
        
        # Анализируем готовность к потокам
        # Получаем историю активности для более точного анализа
        from relove_bot.services.activity_history_service import ActivityHistoryService
        activity_service = ActivityHistoryService(session)
        activity_history = await activity_service.get_conversation_text(user_id, days=30, limit=50)
        
        analysis = await provocative_session.analyze_readiness_for_stream(
            activity_history=activity_history if activity_history else None
        )
        
        if analysis.get("recommended_streams"):
            streams = ", ".join(analysis["recommended_streams"])
            invitation = analysis.get("invitation", "")
            
            await message.answer(
                f"Вижу твою готовность к потокам: {streams}\n\n"
                f"{invitation}\n\n"
                "Подробнее о потоках: /streams"
            )
        
        # Сохраняем метафизический профиль в User
        if hasattr(provocative_session, '_session_service') and provocative_session._db_session_id:
            session_service = provocative_session._session_service
            db_user_session = await session_service.repository.get_session_by_id(provocative_session._db_session_id)
            
            if db_user_session and db_user_session.metaphysical_profile:
                user_repo = UserRepository(session)
                await user_repo.update(user_id, {
                    "metaphysical_profile": db_user_session.metaphysical_profile,
                    "last_journey_stage": None  # Можно определить из сессии, если есть
                })
            
            # Завершаем сессию в БД
            await session_service.complete_session(provocative_session._db_session_id)
        
        # Удаляем из кэша
        if user_id in active_sessions_cache:
            del active_sessions_cache[user_id]
    
    await state.clear()
    await message.answer(
        "Сессия завершена. Помни: я с тобой. 🙏\n\n"
        "Когда будешь готов(а) — возвращайся: /natasha"
    )


@router.callback_query(F.data.startswith("stream_"))
async def handle_stream_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор потока пользователем.
    """
    stream_id = callback.data.replace("stream_", "")
    
    # Информация о потоках
    streams_info = {
        "hero_path": {
            "name": "Путь Героя",
            "description": "Трансформация через прохождение внутреннего пути.",
            "what_to_expect": "Работа с вызовом, отказом, встречей с наставником, пересечением порога.",
            "duration": "3 месяца",
            "format": "Еженедельные сессии + практики"
        },
        "past_lives": {
            "name": "Прошлые Жизни",
            "description": "Работа с планетарными историями и кармическими паттернами.",
            "what_to_expect": "Вскрытие памяти прошлых воплощений, исцеление планетарных травм.",
            "duration": "2 месяца",
            "format": "Глубинные сессии + медитации"
        },
        "heart_opening": {
            "name": "Открытие Сердца",
            "description": "Работа с любовью, принятием и открытостью.",
            "what_to_expect": "Снятие защит, работа со страхом любви, раскрытие сердца.",
            "duration": "2 месяца",
            "format": "Практики открытости + групповые сессии"
        },
        "shadow_work": {
            "name": "Трансформация Тени",
            "description": "Интеграция теневых частей личности.",
            "what_to_expect": "Принятие тьмы, работа с подавленными частями, баланс света и тьмы.",
            "duration": "3 месяца",
            "format": "Индивидуальная работа + практики"
        },
        "awakening": {
            "name": "Пробуждение",
            "description": "Выход из матрицы обыденности.",
            "what_to_expect": "Осознание иллюзий, пробуждение к реальности, выход за пределы.",
            "duration": "4 месяца",
            "format": "Интенсивы + практики осознанности"
        }
    }
    
    stream = streams_info.get(stream_id)
    if not stream:
        await callback.answer("Поток не найден")
        return
    
    await callback.message.edit_text(
        f"**{stream['name']}**\n\n"
        f"{stream['description']}\n\n"
        f"**Что тебя ждёт:**\n{stream['what_to_expect']}\n\n"
        f"**Длительность:** {stream['duration']}\n"
        f"**Формат:** {stream['format']}\n\n"
        f"Это не лёгкий путь. Готов(а) к работе?\n\n"
        "Для регистрации свяжись с @NatashaVolkosh",
        parse_mode="Markdown"
    )
    
    await callback.answer()


@router.message(Command("streams"))
async def show_streams(message: Message):
    """
    Показывает доступные потоки reLove.
    
    Команда: /streams
    """
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


@router.message(Command("analyze_readiness"))
async def analyze_user_readiness(message: Message, session: AsyncSession):
    """
    Анализирует готовность пользователя к потокам на основе истории общения.
    
    Команда: /analyze_readiness
    """
    user_id = message.from_user.id
    
    await message.answer("⏳ Анализирую твою готовность к потокам...")
    
    # Получаем историю сообщений пользователя из UserActivityLog
    from relove_bot.services.activity_history_service import ActivityHistoryService
    
    activity_service = ActivityHistoryService(session)
    
    # Получаем историю общения
    activity_history = await activity_service.get_conversation_text(
        user_id=user_id,
        days=30,
        limit=100
    )
    
    # Получаем текущую сессию, если есть
    session_service = SessionService(session)
    db_session = await session_service.get_active_session(user_id, "provocative")
    
    provocative_session = None
    if db_session:
        provocative_session = await get_or_create_session(user_id, db_session=session)
    
    # Если нет текущей сессии, создаём временную для анализа
    if not provocative_session:
        provocative_session = ProvocativeSession(user_id)
    
    # Анализируем готовность с использованием истории
    analysis = await provocative_session.analyze_readiness_for_stream(
        activity_history=activity_history if activity_history else None
    )
    
    if not analysis.get("recommended_streams"):
        await message.answer(
            "Пока недостаточно данных для анализа.\n\n"
            "Начни сессию с провокативным стилем: /natasha\n"
            "Или проведи диагностику: /diagnostic"
        )
        return
    
    streams = "\n".join([f"• {s}" for s in analysis["recommended_streams"]])
    reasons = "\n".join([f"• {r}" for r in analysis["reasons"]])
    
    await message.answer(
        f"**📊 Анализ готовности к потокам:**\n\n"
        f"**Рекомендованные потоки:**\n{streams}\n\n"
        f"**Признаки готовности:**\n{reasons}\n\n"
        f"{analysis.get('invitation', '')}\n\n"
        "Подробнее о потоках: /streams",
        parse_mode="Markdown"
    )


@router.message(Command("my_session_summary"))
async def show_session_summary(message: Message):
    """
    Показывает итоговую сводку текущей сессии.
    
    Команда: /my_session_summary
    """
    user_id = message.from_user.id
    session = get_or_create_session(user_id)
    
    if session.question_count < 3:
        await message.answer(
            "Сводка ещё не готова.\n\n"
            "Продолжи сессию — ответь хотя бы на несколько вопросов."
        )
        return
    
    await message.answer("Формирую сводку...")
    
    summary = await session.generate_session_summary()
    
    if not summary:
        await message.answer("Не удалось сформировать сводку. Продолжи сессию.")
        return
    
    # Форматируем сводку
    summary_text = "**📊 СВОДКА СЕССИИ**\n\n"
    
    if summary.get("insights"):
        summary_text += "**💡 ИНСАЙТЫ:**\n"
        for insight in summary["insights"]:
            summary_text += f"• {insight}\n"
        summary_text += "\n"
    
    if summary.get("patterns"):
        summary_text += "**🔍 ОБНАРУЖЕННЫЕ ПАТТЕРНЫ:**\n"
        for pattern in summary["patterns"]:
            summary_text += f"• {pattern}\n"
        summary_text += "\n"
    
    if summary.get("core"):
        summary_text += f"**🎯 КОРЕНЬ:**\n{summary['core']}\n\n"
    
    if summary.get("difficulties"):
        summary_text += "**⚠️ ТРУДНОСТИ:**\n"
        for diff in summary["difficulties"]:
            summary_text += f"• {diff}\n"
        summary_text += "\n"
    
    if summary.get("themes"):
        summary_text += "**📖 ОБЩИЕ ТЕМЫ:**\n"
        for theme in summary["themes"]:
            summary_text += f"• {theme}\n"
        summary_text += "\n"
    
    if summary.get("next_steps"):
        summary_text += "**🚀 ПУТЬ ДАЛЬШЕ:**\n"
        for step in summary["next_steps"]:
            summary_text += f"• {step}\n"
    
    summary_text += "\n_Продолжить сессию: просто напиши мне_\n"
    summary_text += "_Завершить: /end_session_"
    
    await message.answer(summary_text, parse_mode="Markdown")


@router.message(Command("my_metaphysical_profile"))
async def show_metaphysical_profile(message: Message):
    """
    Показывает метафизический профиль пользователя.
    
    Команда: /my_metaphysical_profile
    """
    user_id = message.from_user.id
    session = get_or_create_session(user_id)
    
    if not session.metaphysical_profile:
        await message.answer(
            "Метафизический профиль ещё не создан.\n\n"
            "Начни сессию с провокативным стилем и ответь на несколько вопросов: /natasha"
        )
        return
    
    profile = session.metaphysical_profile
    
    # Формируем красивый вывод профиля
    profile_text = f"""
**🌌 Твой Метафизический Профиль**

**Планета:** {profile.get('planetary_type', 'unknown').upper()}
{profile.get('planetary_description', '')}

**Кармический паттерн:** {profile.get('karmic_pattern', 'unknown').upper()}
{profile.get('pattern_manifestations', '')}

**Баланс света/тьмы:**
{profile.get('balance', '')}

**Метафора твоего состояния:**
{profile.get('metaphor', '')}

**Путь трансформации:**
{profile.get('transformation_path', '')}
"""
    
    if profile.get('core_trauma'):
        profile_text += f"\n**Корень:**\n{profile['core_trauma']}"
    
    # Если есть анализ корневой травмы
    if session.core_trauma:
        trauma = session.core_trauma
        profile_text += f"""

**🔥 Корневая Травма**

**Травма:** {trauma.get('trauma', '')}
**Источник:** {trauma.get('source', '')}
**Проявление:** {trauma.get('manifestation', '')}

**Путь исцеления:**
{trauma.get('healing_path', '')}
"""
    
    await message.answer(profile_text, parse_mode="Markdown")
    
    # Предлагаем продолжить работу
    if session.core_trauma and session.question_count < 15:
        instruction = await metaphysical_service.generate_transformation_instruction(
            core_trauma=session.core_trauma,
            metaphysical_profile=profile
        )
        
        if instruction:
            await message.answer(
                f"**Что делать дальше:**\n\n{instruction}\n\n"
                "Продолжить сессию: просто напиши мне.",
                parse_mode="Markdown"
            )
