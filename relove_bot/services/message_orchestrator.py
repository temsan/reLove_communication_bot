"""
Message Orchestrator - координирует все сообщения бота.
Управляет потоком диалога, определяет этап пути и форматирует с UI.
"""
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.db.models import JourneyStageEnum, TriggerTypeEnum
from relove_bot.services.journey_service import JourneyTrackingService
from relove_bot.services.session_service import SessionService
from relove_bot.services.ui_manager import UIManager
from relove_bot.services.llm_service import llm_service
from relove_bot.services.prompts import NATASHA_PROVOCATIVE_PROMPT
from relove_bot.core.journey_behaviors import get_provocation_prompt

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    """Контекст сессии"""
    user_id: int
    session_id: int
    conversation_history: list
    current_stage: Optional[JourneyStageEnum]
    metaphysical_profile: Optional[Dict]
    identified_patterns: list


@dataclass
class BotResponse:
    """Ответ бота"""
    text: str
    keyboard: Optional[Any] = None
    parse_mode: str = "Markdown"


class MessageOrchestrator:
    """Оркестратор сообщений бота"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.journey_service = JourneyTrackingService(session)
        self.session_service = SessionService(session)
        self.ui_manager = UIManager()
    
    async def process_user_message(
        self,
        user_id: int,
        message: str,
        session_type: str = "provocative"
    ) -> BotResponse:
        """
        Обрабатывает входящее сообщение пользователя
        
        Args:
            user_id: ID пользователя
            message: Текст сообщения
            session_type: Тип сессии
        
        Returns:
            BotResponse с ответом
        """
        try:
            # 1. Получаем контекст сессии
            context = await self._get_session_context(user_id, session_type)
            
            if not context:
                return BotResponse(
                    text="Сессия не найдена. Начни с /natasha",
                    keyboard=None
                )
            
            # 2. Определяем текущий этап пути
            if len(context.conversation_history) % 5 == 0:  # Каждые 5 сообщений
                new_stage = await self.journey_service.analyze_journey_stage(
                    user_id,
                    context.conversation_history
                )
                
                if new_stage and new_stage != context.current_stage:
                    await self.journey_service.update_journey_stage(user_id, new_stage)
                    context.current_stage = new_stage
                    logger.info(f"Updated journey stage for user {user_id}: {new_stage}")
            
            # 3. Генерируем ответ с учётом этапа
            response_text = await self._generate_stage_aware_response(
                message,
                context
            )
            
            # 4. Сохраняем сообщения в историю
            await self.session_service.add_message(
                context.session_id,
                "user",
                message
            )
            await self.session_service.add_message(
                context.session_id,
                "assistant",
                response_text
            )
            
            # 5. Форматируем ответ с UI элементами
            formatted_response = await self.format_message_with_ui(
                response_text,
                context.current_stage
            )
            
            return formatted_response
            
        except Exception as e:
            logger.error(f"Error processing user message: {e}", exc_info=True)
            return BotResponse(
                text="Произошла ошибка. Попробуй ещё раз.",
                keyboard=None
            )
    
    async def generate_proactive_message(
        self,
        user_id: int,
        trigger_type: TriggerTypeEnum
    ) -> Optional[BotResponse]:
        """
        Генерирует проактивное сообщение по триггеру
        
        Args:
            user_id: ID пользователя
            trigger_type: Тип триггера
        
        Returns:
            BotResponse или None
        """
        try:
            # Получаем контекст
            context = await self._get_session_context(user_id, "provocative")
            
            if not context:
                return None
            
            # Генерируем сообщение в зависимости от типа триггера
            if trigger_type == TriggerTypeEnum.INACTIVITY_24H:
                message = await self._generate_inactivity_reminder(context)
            elif trigger_type == TriggerTypeEnum.MILESTONE_COMPLETED:
                message = await self._generate_milestone_message(context)
            elif trigger_type == TriggerTypeEnum.PATTERN_DETECTED:
                message = await self._generate_pattern_intervention(context)
            elif trigger_type == TriggerTypeEnum.MORNING_CHECK:
                message = await self._generate_morning_check(context)
            else:
                message = "Привет. Как дела?"
            
            # Форматируем с UI
            formatted_response = await self.format_message_with_ui(
                message,
                context.current_stage
            )
            
            return formatted_response
            
        except Exception as e:
            logger.error(f"Error generating proactive message: {e}", exc_info=True)
            return None
    
    async def format_message_with_ui(
        self,
        message: str,
        stage: Optional[JourneyStageEnum],
        include_progress: bool = False
    ) -> BotResponse:
        """
        Форматирует сообщение с UI элементами
        
        Args:
            message: Текст сообщения
            stage: Текущий этап пути
            include_progress: Добавить индикатор прогресса
        
        Returns:
            BotResponse с форматированием
        """
        # Применяем relove styling
        formatted_text = self.ui_manager.apply_relove_styling(message)
        
        # Добавляем quick replies если есть этап
        keyboard = None
        if stage:
            keyboard = self.ui_manager.create_quick_replies(stage)
        
        return BotResponse(
            text=formatted_text,
            keyboard=keyboard,
            parse_mode="Markdown"
        )
    
    async def _get_session_context(
        self,
        user_id: int,
        session_type: str
    ) -> Optional[SessionContext]:
        """Получает контекст сессии из БД"""
        try:
            user_session = await self.session_service.get_or_create_session(
                user_id,
                session_type
            )
            
            if not user_session:
                return None
            
            # Получаем пользователя для last_journey_stage
            from relove_bot.db.models import User
            from sqlalchemy import select
            
            query = select(User).where(User.id == user_id)
            result = await self.session.execute(query)
            user = result.scalar_one_or_none()
            
            return SessionContext(
                user_id=user_id,
                session_id=user_session.id,
                conversation_history=user_session.conversation_history or [],
                current_stage=user.last_journey_stage if user else None,
                metaphysical_profile=user_session.session_data.get('metaphysical_profile') if user_session.session_data else None,
                identified_patterns=user_session.session_data.get('identified_patterns', []) if user_session.session_data else []
            )
            
        except Exception as e:
            logger.error(f"Error getting session context: {e}", exc_info=True)
            return None
    
    async def _generate_stage_aware_response(
        self,
        user_message: str,
        context: SessionContext
    ) -> str:
        """Генерирует ответ с учётом этапа пути"""
        try:
            # Формируем контекст диалога
            conversation_text = "\n".join([
                f"{'Наташа' if msg['role'] == 'assistant' else 'Человек'}: {msg['content']}"
                for msg in context.conversation_history[-10:]
            ])
            
            # Получаем дополнение к промпту для этапа
            stage_prompt = ""
            if context.current_stage:
                stage_prompt = get_provocation_prompt(context.current_stage)
            
            # Формируем полный промпт
            full_prompt = f"""
{NATASHA_PROVOCATIVE_PROMPT}

{stage_prompt}

ИСТОРИЯ ДИАЛОГА:
{conversation_text}

НОВОЕ СООБЩЕНИЕ ЧЕЛОВЕКА:
{user_message}

Ответь в стиле Наташи — коротко, провокативно, точно.
Максимум 2-3 короткие фразы или 1-2 вопроса.
"""
            
            # Генерируем ответ через LLM
            response = await llm_service.analyze_text(
                prompt=full_prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=200
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating stage-aware response: {e}", exc_info=True)
            return "..."
    
    async def _generate_inactivity_reminder(self, context: SessionContext) -> str:
        """Генерирует напоминание при неактивности"""
        last_message = context.conversation_history[-1]['content'] if context.conversation_history else ""
        
        prompt = f"""
Человек не отвечал 24 часа. Последнее сообщение было: "{last_message}"

Напиши короткое провокативное напоминание в стиле Наташи.
Например: "Ты здесь?" или "Убегаешь?" или "Что случилось?"

Максимум 1-2 предложения.
"""
        
        response = await llm_service.analyze_text(
            prompt=prompt,
            system_prompt=NATASHA_PROVOCATIVE_PROMPT,
            max_tokens=100
        )
        
        return response
    
    async def _generate_milestone_message(self, context: SessionContext) -> str:
        """Генерирует поздравление с завершением этапа"""
        stage_name = context.current_stage.value if context.current_stage else "этап"
        
        prompt = f"""
Человек завершил этап "{stage_name}" на пути героя.

Напиши короткое поздравление с провокацией в стиле Наташи.
Например: "Хорошо. Что дальше?" или "Видишь свой путь?"

Максимум 2-3 предложения.
"""
        
        response = await llm_service.analyze_text(
            prompt=prompt,
            system_prompt=NATASHA_PROVOCATIVE_PROMPT,
            max_tokens=150
        )
        
        return response
    
    async def _generate_pattern_intervention(self, context: SessionContext) -> str:
        """Генерирует вмешательство при обнаружении паттерна"""
        prompt = f"""
Человек избегает ответов - короткие фразы или отрицания.

Напиши прямое вмешательство в стиле Наташи.
Например: "Убегаешь?" или "Это страх или лень?" или "Видишь, что делаешь?"

Максимум 1-2 предложения.
"""
        
        response = await llm_service.analyze_text(
            prompt=prompt,
            system_prompt=NATASHA_PROVOCATIVE_PROMPT,
            max_tokens=100
        )
        
        return response
    
    async def _generate_morning_check(self, context: SessionContext) -> str:
        """Генерирует утреннее сообщение"""
        prompt = f"""
Утро. Напиши короткий вопрос о состоянии в стиле Наташи.
Например: "Как ты?" или "Что чувствуешь сегодня?" или "Готов(а) к работе?"

Максимум 1-2 предложения.
"""
        
        response = await llm_service.analyze_text(
            prompt=prompt,
            system_prompt=NATASHA_PROVOCATIVE_PROMPT,
            max_tokens=100
        )
        
        return response
