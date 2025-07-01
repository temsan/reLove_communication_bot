import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.models import User, JourneyProgress
from ..keyboards.platform import get_platform_keyboard
from ..states.diagnostic_states import DiagnosticStates

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("platform"))
async def show_platform_info(message: Message, state: FSMContext):
    """Показывает информацию о платформе и приглашает посетить"""
    await message.answer(
        "🌟 Добро пожаловать на платформу relove.ru! 🌟\n\n"
        "Здесь вы найдете:\n"
        "• Живые потоки с Наташей\n"
        "• Глубокие трансформационные практики\n"
        "• Сообщество единомышленников\n"
        "• Эксклюзивные материалы\n\n"
        "Хотите узнать больше?",
        reply_markup=get_platform_keyboard()
    )
    await state.set_state(DiagnosticStates.waiting_for_platform_visit)

@router.callback_query(DiagnosticStates.waiting_for_platform_visit)
async def process_platform_visit(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает переход на платформу"""
    try:
        async with AsyncSession() as session:
            # Обновляем статус пользователя
            user = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user.scalar_one_or_none()
            if user:
                user.has_visited_platform = True
                await session.commit()
            
            # Отправляем ссылку на платформу
            await callback.message.edit_text(
                "🎯 Отлично! Вот ваша персональная ссылка на платформу:\n\n"
                "https://relove.ru/join?ref={user_id}\n\n"
                "Там вас ждут:\n"
                "• Персональный анализ вашего психотипа\n"
                "• Рекомендации по развитию\n"
                "• Доступ к эксклюзивным материалам\n"
                "• Возможность присоединиться к живым потокам\n\n"
                "После регистрации вы получите доступ к полному анализу вашего путешествия и рекомендациям от Наташи.",
                reply_markup=get_platform_keyboard(show_purchase=True)
            )
            await state.set_state(DiagnosticStates.waiting_for_purchase)
    except Exception as e:
        logger.error(f"Error processing platform visit: {e}")
        await callback.message.edit_text(
            "Произошла ошибка. Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )

@router.callback_query(DiagnosticStates.waiting_for_purchase)
async def process_flow_purchase(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает интерес к покупке потока"""
    try:
        async with AsyncSession() as session:
            # Обновляем статус пользователя
            user = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user.scalar_one_or_none()
            if user:
                user.has_purchased_flow = True
                await session.commit()
            
            # Отправляем информацию о потоках
            await callback.message.edit_text(
                "🎉 Поздравляем с решением начать трансформацию! 🎉\n\n"
                "Наташа подготовила для вас специальные потоки:\n\n"
                "1. «Путь героя» - базовый поток для начала трансформации\n"
                "2. «Разрушение матрицы» - продвинутый поток для глубоких изменений\n"
                "3. «Возрождение» - интенсив для полной трансформации\n\n"
                "Выберите подходящий поток на платформе, и Наташа проведет вас через все этапы трансформации.\n\n"
                "До встречи на потоках! 🌟"
            )
            await state.clear()
    except Exception as e:
        logger.error(f"Error processing flow purchase: {e}")
        await callback.message.edit_text(
            "Произошла ошибка. Пожалуйста, попробуйте позже или обратитесь в поддержку."
        ) 