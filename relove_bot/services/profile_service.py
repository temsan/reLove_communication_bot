"""
Сервис для массового обновления профилей пользователей.
"""
import logging
from relove_bot.db.repository import UserRepository
from relove_bot.utils.gender import detect_gender
from relove_bot.models.gender import GenderEnum


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
                logger.debug(f'Attempting to get entity for user_id: {user_id}')
                tg_user = await client.get_entity(int(user_id))
            except Exception as e:
                logger.warning(f"Не удалось получить Telegram entity для user {user_id}: {e}")
                # Пробуем получить по username, если он есть в базе
                user_in_db = await self.repo.get_by_id(user_id)
                username = getattr(user_in_db, 'username', None) if user_in_db else None
                if username:
                    try:
                        tg_user = await client.get_entity(username)
                        logger.info(f"Удалось получить entity по username={username} для user_id={user_id}")
                    except Exception as e2:
                        logger.warning(f"Не удалось получить Telegram entity по username={username} для user_id={user_id}: {e2}")
                        tg_user = None
                else:
                    tg_user = None
                    
        user = await self.repo.get_by_id(user_id)
        if not user and tg_user:
            first_name = getattr(tg_user, 'first_name', None)
            last_name = getattr(tg_user, 'last_name', None)
            username = getattr(tg_user, 'username', None)
            # Пропуск, если все три поля отсутствуют
            if not any([first_name, last_name, username]):
                logger.warning(f"Пропуск user_id={user_id}: нет ни first_name, ни last_name, ни username. Не создаём пользователя!")
                return
            user_data = {
                "id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True
            }
            logger.info(f"Пробуем создать пользователя с данными: {user_data}")
            # Требуем хотя бы одно из: first_name или username
            if not (first_name or username):
                logger.warning(f"Пропуск user_id={user_id}: отсутствуют и first_name, и username. Не создаём пользователя!")
                return
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
        
        result = {}
        
        if not user_has_summary:
            # Получаем посты из личного канала
            try:
                channel_data = await get_personal_channel_posts(user_id)
                if channel_data:
                    posts = channel_data.get("posts", [])
                    photo_summaries = channel_data.get("photo_summaries", [])
                    if posts:
                        user.profile_summary = "\n".join(posts)
                    if photo_summaries:
                        user.markers = user.markers or {}
                        user.markers['photo_summaries'] = photo_summaries
                    await self.repo.session.commit()
                    result['summary'] = user.profile_summary
            except Exception as e:
                logger.warning(f"Не удалось получить посты из личного канала для user {user_id}: {e}")

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
                # Сохраняем потоки в поле streams модели User
                user.streams = streams
                await self.repo.session.commit()
                result['streams'] = streams
            except Exception as e:
                logger.warning(f"Не удалось определить потоки через LLM для user {user_id}: {e}")

        if not user_has_gender:
            # Если это бот, устанавливаем женский пол
            if tg_user and getattr(tg_user, 'bot', False):
                gender = GenderEnum.female
                logger.info(f"Пользователь {user_id} является ботом, установлен женский пол")
            else:
                gender = await detect_gender(tg_user) if tg_user else GenderEnum.female
            await self.repo.update_gender(user_id, gender)
            result['gender'] = gender

        return result
