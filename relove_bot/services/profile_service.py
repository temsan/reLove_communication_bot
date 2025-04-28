"""
Сервис для массового обновления профилей пользователей.
"""
import logging
from relove_bot.db.repository import UserRepository
from relove_bot.utils.gender import detect_gender


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
        if tg_user is None:
            try:
                tg_user = await client.get_entity(user_id)
            except Exception as e:
                logger.warning(f"Не удалось получить Telegram entity для user {user_id}: {e}")
                tg_user = None
        user = await self.repo.get_by_id(user_id)
        if not user and tg_user:
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
            self.repo.session.add(user)
            await self.repo.session.commit()
            logger.info(f"Создан новый пользователь {user_id} ({user.username})")
        user_has_summary = user and user.profile_summary and user.profile_summary.strip()
        user_has_gender = user and user.gender and str(user.gender) not in ('', 'unknown', 'None')

        if user_has_summary and user_has_gender:
            logger.info(f"User {user_id} уже имеет summary и gender, пропускаем.")
            return 'skipped'

        summary = None
        gender = None
        result = {}

        posts = None
        if not user_has_summary:
            posts = await get_user_posts_in_channel(main_channel_id, user_id)
            summary = await get_full_psychological_summary(
                user_id=user_id,
                main_channel_id=main_channel_id,
                tg_user=tg_user,
                posts=posts
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

            # --- Определяем потоки через LLM по тем же постам ---
            try:
                llm_service = LLMService()
                posts_text = '\n'.join(posts) if posts else ''
                prompt = (
                    "На основе следующих постов пользователя определи, к каким потокам он относится: женский, мужской, смешанный. "
                    "Ответь списком через запятую только из этих вариантов.\nПосты пользователя:\n" + posts_text
                )
                streams_str = await llm_service.analyze_text(prompt, system_prompt="Определи потоки пользователя", max_tokens=16)
                streams = [s.strip().capitalize() for s in streams_str.split(',') if s.strip()]
                if hasattr(user, 'markers') and isinstance(user.markers, dict):
                    user.markers['streams'] = streams
                elif hasattr(user, 'streams'):
                    user.streams = streams
                await self.repo.session.commit()
                result['streams'] = streams
            except Exception as e:
                logger.warning(f"Не удалось определить потоки через LLM для user {user_id}: {e}")

        if not user_has_gender:
    
            gender = await detect_gender(tg_user) if tg_user else 'unknown'
            await self.repo.update_gender(user_id, gender)
            result['gender'] = gender

        return result
