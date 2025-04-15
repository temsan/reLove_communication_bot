import logging
from aiogram import Router, types
from aiogram.filters import Command
from ..rag.llm import generate_summary, generate_rag_answer
from ..rag.pipeline import get_user_context
from ..db.session import SessionLocal
from ..db.models import UserActivityLog, User
from datetime import datetime

logger = logging.getLogger(__name__)
router = Router()

from ..rag.pipeline import get_profile_summary
from ..db.vector import search_similar_users
from ..rag.llm import get_text_embedding
import logging

@router.message()
async def handle_message(message: types.Message):
    try:
        summary = await generate_summary(message.text)
        async with SessionLocal() as session:
            # Сохраняем summary
            log = UserActivityLog(
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                activity_type="message",
                timestamp=datetime.utcnow(),
                details={"message_id": message.message_id},
                summary=summary
            )
            session.add(log)
            # Получаем пользователя и его этап пути героя
            user = await session.get(User, message.from_user.id)
            relove_context = (user.context or {}).get("relove_context") if user and user.context else None
            profile_summary = await get_profile_summary(message.from_user.id, session)
            await session.commit()
        # Генерируем персонализированный ответ с учетом контекста
        if relove_context:
            prompt = (
                f"Контекст пользователя: {relove_context}\n"
                f"Новое сообщение пользователя: {message.text}\n"
                f"Дай персонализированную обратную связь для пробуждения и развития в потоке reLove."
            )
        else:
            prompt = (
                f"Профиль пользователя (summary): {profile_summary}\n"
                f"Новое сообщение пользователя: {message.text}\n"
                f"Дай персонализированную обратную связь для пробуждения и развития в потоке reLove."
            )
        feedback = await generate_rag_answer(context="", question=prompt)
        await message.answer(feedback)
    except Exception as e:
        logging.error(f"Ошибка в handle_message: {e}")
        await message.answer("Произошла ошибка при обработке сообщения. Попробуйте позже.")

@router.message(commands=["similar"])
async def handle_similar(message: types.Message):
    try:
        args = message.get_args().strip()
        top_k = 5
        if args.isdigit():
            top_k = int(args)
        async with SessionLocal() as session:
            profile_summary = await get_profile_summary(message.from_user.id, session)
        if not profile_summary:
            await message.answer("Ваш профиль ещё не проанализирован. Напишите несколько сообщений для формирования профиля.")
            return
        query_embedding = await get_text_embedding(profile_summary)
        hits = search_similar_users(query_embedding, top_k=top_k)
        if not hits:
            await message.answer("Похожие пользователи не найдены.")
            return
        response = "Похожие пользователи:\n"
        for hit in hits:
            user_id = hit.id
            username = hit.payload.get("username") if hit.payload else None
            hero_stage = hit.payload.get("hero_path_stage") if hit.payload else None
            response += f"ID: {user_id} | username: {username or '-'} | этап: {hero_stage or '-'}\n"
        await message.answer(response)
    except Exception as e:
        logging.error(f"Ошибка в /similar: {e}")
        await message.answer("Ошибка при поиске похожих пользователей. Попробуйте позже.")