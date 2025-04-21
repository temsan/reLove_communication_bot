"""
Сервис для массового обновления профилей пользователей.
"""
import logging
from relove_bot.db.repository import UserRepository
from relove_bot.utils.gender import detect_gender
from relove_bot.services import telegram_service

logger = logging.getLogger(__name__)

class ProfileService:
    def __init__(self, session):
        self.repo = UserRepository(session)

    @staticmethod
    def validate_user_fields(user_dict):
        missing = []
        for field in ("first_name", "last_name", "username"):
            if not user_dict.get(field):
                missing.append(field)
        return missing

    async def process_user(self, user_id, main_channel_id, tg_user=None):
        user = await self.repo.get_by_id(user_id)
        if not user and tg_user:
            # Создаём нового пользователя
            from relove_bot.db.models import User
            user_data = {
                "id": user_id,
                "username": getattr(tg_user, 'username', None),
                "first_name": getattr(tg_user, 'first_name', None),
                "last_name": getattr(tg_user, 'last_name', None),
                "is_active": True
            }
            missing_fields = self.validate_user_fields(user_data)
            if missing_fields:
                logger.warning(f"Отсутствуют обязательные поля для пользователя {user_id}: {', '.join(missing_fields)}. Пропускаем создание пользователя.")
                return
            user = User(**user_data)
            user = User(
                id=user_id,
                username=getattr(tg_user, 'username', None),
                first_name=getattr(tg_user, 'first_name', None),
                last_name=getattr(tg_user, 'last_name', None),
                is_active=True
            )
            self.repo.session.add(user)
            await self.repo.session.commit()
            logger.info(f"Создан новый пользователь {user_id} ({user.username})")
        user_has_summary = user and user.profile_summary and user.profile_summary.strip()
        user_has_gender = user and user.gender and str(user.gender) not in ('', 'unknown', 'None')

        if user_has_summary and user_has_gender:
            logger.info(f"User {user_id} уже имеет summary и gender, пропускаем.")
            return 'skipped'

        if tg_user:
            first_name = getattr(tg_user, 'first_name', None)
            last_name = getattr(tg_user, 'last_name', None)
            username = getattr(tg_user, 'username', None)
        else:
            first_name = last_name = username = None

        summary = None
        gender = None
        result = {}

        if not user_has_summary:
            summary = await telegram_service.get_full_psychological_summary(
                user_id=user_id,
                main_channel_id=main_channel_id,
                tg_user=tg_user
            )
            refusal_phrases = [
                "i'm sorry, i can't help",
                "i'm sorry, i can't assist",
                "i can't help with that",
                "i can't assist with that",
                "я не могу помочь",
                "не могу помочь",
                "не могу выполнить",
                "не могу анализировать",
                "отказ",
                "извините, я не могу помочь с этой задачей"
            ]
            if not summary or any(phrase in summary.lower() for phrase in refusal_phrases):
                logger.warning(f"LLM отказался генерировать summary для user {user_id} (summary='{summary}'). Пропуск записи в БД.")
                result['failed'] = True
                return result
            await self.repo.update_summary(user_id, summary)
            result['summary'] = summary

        if not user_has_gender:
            gender = await detect_gender(tg_user)
            await self.repo.update_gender(user_id, gender)
            result['gender'] = gender

        return result
