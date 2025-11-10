"""
Natasha Proactive Service - расширение для stage-aware провокаций.
"""
import logging
from typing import Optional, List, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.db.models import JourneyStageEnum
from relove_bot.services.llm_service import llm_service
from relove_bot.services.prompts import NATASHA_PROVOCATIVE_PROMPT
from relove_bot.core.journey_behaviors import get_provocation_prompt

logger = logging.getLogger(__name__)


class NatashaProactiveService:
    """Сервис для stage-aware провокаций в стиле Наташи"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def generate_stage_aware_response(
        self,
        user_message: str,
        stage: JourneyStageEnum,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Генерирует ответ с учётом этапа пути героя
        
        Args:
            user_message: Сообщение пользователя
            stage: Текущий этап пути
            conversation_history: История диалога
        
        Returns:
            Ответ в стиле Наташи
        """
        try:
            # Получаем дополнение к промпту для этапа
            stage_prompt = get_provocation_prompt(stage)
            
            # Формируем контекст
            conversation_text = "\n".join([
                f"{'Наташа' if msg['role'] == 'assistant' else 'Человек'}: {msg['content']}"
                for msg in conversation_history[-10:]
            ])
            
            # Полный промпт
            full_prompt = f"""
{NATASHA_PROVOCATIVE_PROMPT}

{stage_prompt}

ИСТОРИЯ ДИАЛОГА:
{conversation_text}

НОВОЕ СООБЩЕНИЕ:
{user_message}

Ответь в стиле Наташи с учётом этапа пути.
Максимум 2-3 короткие фразы.
"""
            
            response = await llm_service.analyze_text(
                prompt=full_prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=200
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating stage-aware response: {e}", exc_info=True)
            return "..."
    
    async def generate_proactive_reminder(
        self,
        user_id: int,
        last_message: str,
        hours_inactive: int
    ) -> str:
        """
        Генерирует проактивное напоминание для неактивного пользователя
        
        Args:
            user_id: ID пользователя
            last_message: Последнее сообщение
            hours_inactive: Часов неактивности
        
        Returns:
            Провокативное напоминание
        """
        try:
            prompt = f"""
Человек не отвечал {hours_inactive} часов.
Последнее сообщение: "{last_message}"

Напиши короткое провокативное напоминание в стиле Наташи.
Учти время неактивности - чем дольше, тем более прямой вопрос.

Примеры:
- "Ты здесь?"
- "Убегаешь?"
- "Что случилось?"
- "Страшно стало?"

Максимум 1-2 предложения.
"""
            
            response = await llm_service.analyze_text(
                prompt=prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=100
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating proactive reminder: {e}", exc_info=True)
            return "Ты здесь?"
    
    async def generate_milestone_message(
        self,
        stage_completed: JourneyStageEnum,
        next_stage: JourneyStageEnum
    ) -> str:
        """
        Генерирует поздравление с завершением этапа
        
        Args:
            stage_completed: Завершённый этап
            next_stage: Следующий этап
        
        Returns:
            Поздравление с провокацией
        """
        try:
            prompt = f"""
Человек завершил этап "{stage_completed.value}".
Следующий этап: "{next_stage.value}".

Напиши короткое поздравление с провокацией в стиле Наташи.

Примеры:
- "Хорошо. Что дальше?"
- "Видишь свой путь?"
- "Готов(а) к следующему?"

Максимум 2-3 предложения.
"""
            
            response = await llm_service.analyze_text(
                prompt=prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=150
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating milestone message: {e}", exc_info=True)
            return "Хорошо. Что дальше?"
    
    async def detect_avoidance_pattern(
        self,
        conversation: List[Dict[str, str]]
    ) -> Optional[str]:
        """
        Обнаруживает паттерны избегания в диалоге
        
        Args:
            conversation: История диалога
        
        Returns:
            Описание паттерна или None
        """
        try:
            if len(conversation) < 3:
                return None
            
            # Берём последние 5 сообщений
            recent = conversation[-5:]
            conversation_text = "\n".join([
                f"{'Наташа' if msg['role'] == 'assistant' else 'Человек'}: {msg['content']}"
                for msg in recent
            ])
            
            prompt = f"""
Проанализируй диалог на паттерны избегания:
- Короткие ответы (менее 10 символов)
- Отрицания ("не знаю", "не понимаю")
- Откладывание ("потом", "может быть")
- Рационализация (оправдания)

ДИАЛОГ:
{conversation_text}

Если видишь паттерн избегания, опиши его одним словом:
"отрицание", "откладывание", "рационализация", "бегство"

Если паттерна нет, ответь "нет".
"""
            
            response = await llm_service.analyze_text(
                prompt=prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=50
            )
            
            if response.lower().strip() == "нет":
                return None
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error detecting avoidance pattern: {e}", exc_info=True)
            return None
