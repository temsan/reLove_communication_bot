import logging
from aiogram import Router, types
from aiogram.filters import Command
from ..rag.llm import generate_summary, generate_rag_answer
from ..rag.pipeline import get_user_context
from ..db.session import SessionLocal
from ..db.models import UserActivityLog
from datetime import datetime

logger = logging.getLogger(__name__)
router = Router()

@router.message()
async def handle_message(message: types.Message):
    summary = await generate_summary(message.text)
    async with SessionLocal() as session:
        log = UserActivityLog(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            activity_type="message",
            timestamp=datetime.utcnow(),
            details={"message_id": message.message_id},
            summary=summary
        )
        session.add(log)
        await session.commit()

@router.message(Command(commands=["ask"]))
async def handle_ask(message: types.Message):
    user_id = message.from_user.id
    user_question = message.get_args()
    context = await get_user_context(user_id)
    answer = await generate_rag_answer(context, user_question)
    await message.answer(answer)