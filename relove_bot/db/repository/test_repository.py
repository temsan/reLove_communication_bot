from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from relove_bot.db.models.personality_test import TestResult, TestAnswer
from relove_bot.db.models.user import User

class TestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_test_answer(self, user_id: int, question_id: int, answer: str) -> TestAnswer:
        """Сохранить ответ пользователя на вопрос теста"""
        test_answer = TestAnswer(
            user_id=user_id,
            question_id=question_id,
            answer=answer
        )
        self.session.add(test_answer)
        await self.session.commit()
        await self.session.refresh(test_answer)
        return test_answer

    async def save_test_result(self, user_id: int, hero_journey_stage: str,
                             personality_type: str, description: str,
                             recommendations: List[str]) -> TestResult:
        """Сохранить результаты теста пользователя"""
        test_result = TestResult(
            user_id=user_id,
            hero_journey_stage=hero_journey_stage,
            personality_type=personality_type,
            description=description,
            recommendations=recommendations
        )
        self.session.add(test_result)
        await self.session.commit()
        await self.session.refresh(test_result)
        return test_result

    async def get_user_test_answers(self, user_id: int) -> List[TestAnswer]:
        """Получить все ответы пользователя на вопросы теста"""
        query = select(TestAnswer).where(TestAnswer.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_user_test_result(self, user_id: int) -> Optional[TestResult]:
        """Получить последний результат теста пользователя"""
        query = (
            select(TestResult)
            .where(TestResult.user_id == user_id)
            .order_by(TestResult.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        query = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_user(self, telegram_id: int, username: Optional[str] = None,
                         first_name: Optional[str] = None,
                         last_name: Optional[str] = None) -> User:
        """Создать нового пользователя"""
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user 