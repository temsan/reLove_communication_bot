from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from relove_bot.db.models import DiagnosticResult, DiagnosticQuestion, PsychotypeEnum, JourneyStageEnum, UserActivityLog

class DiagnosticRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_diagnostic_result(
        self,
        user_id: int,
        psychotype: PsychotypeEnum,
        journey_stage: JourneyStageEnum,
        answers: Dict[str, str],
        description: Optional[str] = None,
        strengths: Optional[List[str]] = None,
        challenges: Optional[List[str]] = None,
        emotional_triggers: Optional[List[str]] = None,
        logical_patterns: Optional[List[str]] = None,
        current_state: Optional[str] = None,
        next_steps: Optional[List[str]] = None,
        emotional_state: Optional[str] = None,
        resistance_points: Optional[List[str]] = None,
        recommended_stream: Optional[str] = None,
        stream_description: Optional[str] = None
    ) -> DiagnosticResult:
        """Сохраняет результат диагностики"""
        result = DiagnosticResult(
            user_id=user_id,
            psychotype=psychotype,
            journey_stage=journey_stage,
            answers=answers,
            description=description,
            strengths=strengths,
            challenges=challenges,
            emotional_triggers=emotional_triggers,
            logical_patterns=logical_patterns,
            current_state=current_state,
            next_steps=next_steps,
            emotional_state=emotional_state,
            resistance_points=resistance_points,
            recommended_stream=recommended_stream,
            stream_description=stream_description
        )
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_user_diagnostic_results(self, user_id: int) -> List[DiagnosticResult]:
        """Получает все результаты диагностики пользователя"""
        query = select(DiagnosticResult).where(DiagnosticResult.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_diagnostic_result(self, user_id: int) -> Optional[DiagnosticResult]:
        """Получает последний результат диагностики пользователя"""
        query = (
            select(DiagnosticResult)
            .where(DiagnosticResult.user_id == user_id)
            .order_by(DiagnosticResult.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_questions(self) -> List[DiagnosticQuestion]:
        """Получает все активные вопросы для диагностики"""
        query = (
            select(DiagnosticQuestion)
            .where(DiagnosticQuestion.is_active == True)
            .order_by(DiagnosticQuestion.order)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create_question(
        self,
        text: str,
        options: Dict[str, str],
        order: int,
        emotional_context: Optional[str] = None,
        logical_context: Optional[str] = None
    ) -> DiagnosticQuestion:
        """Создает новый вопрос для диагностики"""
        question = DiagnosticQuestion(
            text=text,
            options=options,
            order=order,
            emotional_context=emotional_context,
            logical_context=logical_context
        )
        self.session.add(question)
        await self.session.commit()
        await self.session.refresh(question)
        return question

    async def update_question(
        self,
        question_id: int,
        text: Optional[str] = None,
        options: Optional[Dict[str, str]] = None,
        order: Optional[int] = None,
        is_active: Optional[bool] = None,
        emotional_context: Optional[str] = None,
        logical_context: Optional[str] = None
    ) -> Optional[DiagnosticQuestion]:
        """Обновляет вопрос диагностики"""
        update_data = {}
        if text is not None:
            update_data["text"] = text
        if options is not None:
            update_data["options"] = options
        if order is not None:
            update_data["order"] = order
        if is_active is not None:
            update_data["is_active"] = is_active
        if emotional_context is not None:
            update_data["emotional_context"] = emotional_context
        if logical_context is not None:
            update_data["logical_context"] = logical_context

        if not update_data:
            return None

        query = (
            update(DiagnosticQuestion)
            .where(DiagnosticQuestion.id == question_id)
            .values(**update_data)
            .returning(DiagnosticQuestion)
        )
        result = await self.session.execute(query)
        await self.session.commit()
        return result.scalar_one_or_none()

    async def get_user_history_summary(self, user_id: int, days: int = 30, limit: int = 100) -> Dict[str, Any]:
        """Получает сводку по истории общения пользователя с ботом"""
        time_threshold = datetime.utcnow() - timedelta(days=days)
        
        # Получаем последние записи активности
        query = (
            select(UserActivityLog)
            .where(
                UserActivityLog.user_id == user_id,
                UserActivityLog.timestamp >= time_threshold
            )
            .order_by(desc(UserActivityLog.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(query)
        activities = result.scalars().all()
        
        if not activities:
            return {
                "status": "no_data",
                "message": f"Нет данных о деятельности за последние {days} дней",
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
        
        # Анализируем активность
        activity_summary = self._analyze_activity(activities)
        
        # Формируем итоговый результат
        return {
            "status": "success",
            "total_activities": len(activities),
            "time_period": {
                "start": min(a.timestamp.isoformat() for a in activities),
                "end": max(a.timestamp.isoformat() for a in activities),
                "days": days
            },
            "activity_summary": activity_summary,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }

    def _analyze_activity(self, activities: List[UserActivityLog]) -> Dict[str, Any]:
        """Анализирует активность пользователя"""
        analysis = {
            "total_interactions": len(activities),
            "last_interaction": activities[0].timestamp.isoformat() if activities else None,
            "interaction_types": {},
            "topics": {},
            "emotional_states": {},
            "recommendations": []
        }
        
        for activity in activities:
            # Анализ типов взаимодействия
            interaction_type = activity.interaction_type
            analysis["interaction_types"][interaction_type] = analysis["interaction_types"].get(interaction_type, 0) + 1
            
            # Анализ тем
            if activity.topic:
                analysis["topics"][activity.topic] = analysis["topics"].get(activity.topic, 0) + 1
            
            # Анализ эмоциональных состояний
            if activity.emotional_state:
                analysis["emotional_states"][activity.emotional_state] = analysis["emotional_states"].get(activity.emotional_state, 0) + 1
        
        # Формируем рекомендации на основе анализа
        if analysis["interaction_types"].get("diagnostic", 0) == 0:
            analysis["recommendations"].append("Попробуйте пройти диагностику для получения персональных рекомендаций")
        
        if analysis["interaction_types"].get("stream", 0) == 0:
            analysis["recommendations"].append("Присоединитесь к нашим потокам для более глубокой работы над собой")
        
        return analysis

    def _generate_diagnostic_recommendations(self, psychotype: str, journey_stage: str) -> List[str]:
        """Сгенерировать рекомендации на основе психотипа и этапа пути"""
        recommendations = {
            ("matrix", "ordinary_world"): [
                "Начните с потока 'Пробуждение' для знакомства с новыми возможностями",
                "Изучите базовые практики осознанности и медитации",
                "Присоединитесь к сообществу единомышленников для поддержки"
            ],
            ("matrix", "call_to_adventure"): [
                "Пройдите поток 'Трансформация восприятия'",
                "Начните вести дневник осознанности",
                "Исследуйте новые способы взаимодействия с реальностью"
            ],
            ("seeker", "refusal"): [
                "Пройдите поток 'Преодоление страхов и ограничений'",
                "Работайте с практиками принятия и трансформации",
                "Найдите поддержку в группе единомышленников"
            ],
            ("seeker", "meeting_mentor"): [
                "Присоединитесь к потоку 'Интеграция полярностей'",
                "Освойте практики баланса мужской и женской энергии",
                "Начните делиться своим опытом с другими"
            ],
            ("transformer", "crossing_threshold"): [
                "Пройдите продвинутый поток 'Мастерство трансформации'",
                "Начните помогать другим на их пути",
                "Интегрируйте духовный опыт в повседневную жизнь"
            ]
        }
        
        # Добавляем общие рекомендации для всех типов
        common_recommendations = [
            "Регулярно практикуйте медитацию и осознанность",
            "Ведите дневник трансформации",
            "Участвуйте в групповых практиках"
        ]
        
        # Получаем специфические рекомендации
        specific_recommendations = recommendations.get((psychotype, journey_stage), [
            "Начните с базового потока 'Пробуждение'",
            "Изучите практики осознанности",
            "Присоединитесь к сообществу"
        ])
        
        # Объединяем рекомендации
        return specific_recommendations + common_recommendations 