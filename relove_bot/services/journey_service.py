"""
Сервис для отслеживания пути героя пользователя.
Анализирует текущий этап и обновляет прогресс.
"""
import logging
from typing import Optional, List, Dict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.db.models import User, JourneyProgress, JourneyStageEnum
from relove_bot.services.llm_service import llm_service
from relove_bot.core.hero_journey import JOURNEY_STAGES

logger = logging.getLogger(__name__)


class JourneyTrackingService:
    """Сервис для отслеживания пути героя"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def analyze_journey_stage(
        self,
        user_id: int,
        conversation_history: List[Dict[str, str]]
    ) -> Optional[JourneyStageEnum]:
        """
        Анализирует текущий этап пути героя на основе диалога.
        
        Args:
            user_id: ID пользователя
            conversation_history: История диалога
        
        Returns:
            JourneyStageEnum или None если не удалось определить
        """
        try:
            # Получаем текущий этап пользователя
            user = await self.get_user(user_id)
            current_stage = user.last_journey_stage if user else None
            
            # Формируем контекст диалога
            conversation_text = "\n".join([
                f"{'Ассистент' if msg['role'] == 'assistant' else 'Пользователь'}: {msg['content']}"
                for msg in conversation_history[-10:]  # Последние 10 сообщений
            ])
            
            # Формируем промпт для LLM
            prompt = self.build_stage_analysis_prompt(current_stage, conversation_text)
            
            # Анализируем через LLM
            response = await llm_service.analyze_text(prompt, max_tokens=200)
            
            if not response:
                return None
            
            # Парсим ответ и определяем этап
            new_stage = self.parse_stage_from_response(response)
            
            return new_stage
            
        except Exception as e:
            logger.error(f"Error analyzing journey stage for user {user_id}: {e}")
            return None
    
    def build_stage_analysis_prompt(
        self,
        current_stage: Optional[JourneyStageEnum],
        conversation_text: str
    ) -> str:
        """Формирует промпт для анализа этапа"""
        
        # Описания этапов из hero_journey.py
        stages_description = "\n".join([
            f"- {stage['name']}: {stage['description']}"
            for stage in JOURNEY_STAGES
        ])
        
        current_stage_text = f"Текущий этап: {current_stage.value}" if current_stage else "Этап не определён"
        
        prompt = f"""Определи этап пути героя по Кэмпбеллу на основе диалога.

{current_stage_text}

ЭТАПЫ ПУТИ ГЕРОЯ:
{stages_description}

ДИАЛОГ:
{conversation_text}

ЗАДАЧА:
Проанализируй диалог и определи, на каком этапе пути героя находится человек.
Ответь ТОЛЬКО названием этапа из списка выше.

Если этап изменился с текущего - укажи новый.
Если остался тот же - укажи текущий.

ОТВЕТ (только название этапа):"""
        
        return prompt
    
    def parse_stage_from_response(self, response: str) -> Optional[JourneyStageEnum]:
        """Парсит этап из ответа LLM"""
        response = response.strip()
        
        # Пробуем найти этап по значению
        for stage in JourneyStageEnum:
            if stage.value.lower() in response.lower():
                return stage
        
        # Пробуем найти по имени enum
        for stage in JourneyStageEnum:
            if stage.name.lower() in response.lower():
                return stage
        
        logger.warning(f"Could not parse stage from response: {response}")
        return None
    
    async def update_journey_stage(
        self,
        user_id: int,
        new_stage: JourneyStageEnum
    ):
        """
        Обновляет этап пути героя пользователя.
        
        Args:
            user_id: ID пользователя
            new_stage: Новый этап
        """
        try:
            # Получаем пользователя
            user = await self.get_user(user_id)
            
            if not user:
                logger.warning(f"User {user_id} not found")
                return
            
            old_stage = user.last_journey_stage
            
            # Обновляем этап
            user.last_journey_stage = new_stage
            
            # Создаём запись в JourneyProgress
            progress = JourneyProgress(
                user_id=user_id,
                current_stage=new_stage,
                stage_start_time=datetime.now()
            )
            
            # Добавляем старый этап в completed_stages
            if old_stage:
                progress.completed_stages = [old_stage.value]
            
            self.session.add(progress)
            await self.session.commit()
            
            logger.info(
                f"Updated journey stage for user {user_id}: "
                f"{old_stage.value if old_stage else 'None'} -> {new_stage.value}"
            )
            
        except Exception as e:
            logger.error(f"Error updating journey stage for user {user_id}: {e}")
            await self.session.rollback()
    
    async def get_journey_progress(self, user_id: int) -> List[JourneyProgress]:
        """
        Получает прогресс пути героя пользователя.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Список записей JourneyProgress
        """
        try:
            query = select(JourneyProgress).where(
                JourneyProgress.user_id == user_id
            ).order_by(JourneyProgress.stage_start_time.desc())
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting journey progress for user {user_id}: {e}")
            return []
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """Получает пользователя по ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
