from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from relove_bot.db.repository.test_repository import TestRepository

class HeroJourneyStage(Enum):
    ORDINARY_WORLD = "Обычный мир"
    CALL_TO_ADVENTURE = "Зов к приключениям"
    REFUSAL_OF_CALL = "Отказ от зова"
    MEETING_WITH_MENTOR = "Встреча с наставником"
    CROSSING_FIRST_THRESHOLD = "Пересечение первого порога"
    TESTS_ALLIES_ENEMIES = "Испытания, союзники, враги"
    APPROACH_TO_INNERMOST_CAVE = "Приближение к сокровенной пещере"
    ORDEAL = "Испытание"
    REWARD = "Награда"
    ROAD_BACK = "Дорога назад"
    RESURRECTION = "Воскрешение"
    RETURN_WITH_ELIXIR = "Возвращение с эликсиром"

@dataclass
class TestResult:
    hero_journey_stage: HeroJourneyStage
    personality_type: str
    description: str
    recommendations: List[str]

class PersonalityTestService:
    def __init__(self, test_repository: TestRepository):
        self.test_repository = test_repository
        self.questions = [
            {
                "id": 1,
                "text": "Как вы обычно реагируете на новые вызовы?",
                "options": [
                    "С энтузиазмом и готовностью действовать",
                    "С осторожностью и анализом ситуации",
                    "С тревогой и желанием избежать изменений",
                    "С интересом, но без спешки"
                ]
            },
            {
                "id": 2,
                "text": "Что для вас важнее в жизни?",
                "options": [
                    "Достижение целей и успех",
                    "Гармония и стабильность",
                    "Творчество и самовыражение",
                    "Помощь другим и служение"
                ]
            },
            {
                "id": 3,
                "text": "Как вы справляетесь с трудностями?",
                "options": [
                    "Активно ищу решение",
                    "Анализирую ситуацию и планирую",
                    "Ищу поддержку у близких",
                    "Жду, пока ситуация разрешится сама"
                ]
            }
        ]
        
    async def get_next_question(self, telegram_id: int) -> Optional[Dict]:
        """Получить следующий вопрос для пользователя"""
        user = await self.test_repository.get_user_by_telegram_id(telegram_id)
        if not user:
            return None
            
        answers = await self.test_repository.get_user_test_answers(user.id)
        answered_question_ids = {answer.question_id for answer in answers}
        
        for question in self.questions:
            if question["id"] not in answered_question_ids:
                return question
                
        return None
        
    async def process_answer(self, telegram_id: int, question_id: int, answer: str) -> None:
        """Обработать ответ пользователя"""
        user = await self.test_repository.get_user_by_telegram_id(telegram_id)
        if not user:
            return
            
        await self.test_repository.save_test_answer(user.id, question_id, answer)
        
    async def get_test_result(self, telegram_id: int) -> TestResult:
        """Получить результаты теста для пользователя"""
        user = await self.test_repository.get_user_by_telegram_id(telegram_id)
        if not user:
            raise ValueError("User not found")
            
        answers = await self.test_repository.get_user_test_answers(user.id)
        
        # Простая логика определения результатов на основе ответов
        # В реальном приложении здесь должна быть более сложная логика
        personality_type = "Исследователь"  # Пример
        hero_journey_stage = HeroJourneyStage.CALL_TO_ADVENTURE
        description = "Вы находитесь на этапе, когда начинаете осознавать необходимость изменений в своей жизни."
        
        recommendations = self.generate_recommendations(TestResult(
            hero_journey_stage=hero_journey_stage,
            personality_type=personality_type,
            description=description,
            recommendations=[]
        ))
        
        # Сохраняем результат в базу данных
        await self.test_repository.save_test_result(
            user.id,
            hero_journey_stage.value,
            personality_type,
            description,
            recommendations
        )
        
        return TestResult(
            hero_journey_stage=hero_journey_stage,
            personality_type=personality_type,
            description=description,
            recommendations=recommendations
        )
        
    def generate_recommendations(self, result: TestResult) -> List[str]:
        """Сгенерировать рекомендации на основе результатов теста"""
        recommendations = [
            "Для более глубокого понимания вашего пути и дальнейшего развития, "
            "рекомендуем присоединиться к нашим живым потокам с Наташей.",
            "На платформе вы сможете получить персонализированные рекомендации "
            "и поддержку в вашем развитии.",
            f"Ваш текущий этап на пути героя ({result.hero_journey_stage.value}) "
            "показывает, что вы готовы к новым открытиям и трансформациям.",
            "Присоединяйтесь к нашему сообществу, чтобы получить поддержку "
            "и вдохновение от единомышленников."
        ]
        return recommendations 