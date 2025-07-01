import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.psychological_types import PsychotypeEnum, PSYCHOLOGICAL_TYPES
from ..core.hero_journey import JourneyStageEnum, JOURNEY_STAGES
from ..keyboards.psychological import (
    get_psychological_type_keyboard,
    get_journey_stage_keyboard,
    get_question_keyboard
)
from ..db.models import User, DiagnosticResult
from ..states.diagnostic_states import DiagnosticStates

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start_journey"))
async def start_psychological_journey(message: Message, state: FSMContext):
    """Начало психологического путешествия"""
    await message.answer(
        "Добро пожаловать в психологическое путешествие! 🧠✨\n\n"
        "Давайте определим ваш психологический тип, чтобы лучше понять, "
        "как помочь вам в вашем пути.\n\n"
        "Выберите тип, который вам ближе всего:",
        reply_markup=get_psychological_type_keyboard()
    )
    await state.set_state(DiagnosticStates.WAITING_FOR_TYPE)

@router.callback_query(DiagnosticStates.WAITING_FOR_TYPE)
async def process_psychological_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора психологического типа"""
    try:
        psychological_type = PsychotypeEnum(callback.data)
        await state.update_data(psychological_type=psychological_type)
        
        profile = PSYCHOLOGICAL_TYPES[psychological_type]
        await callback.message.edit_text(
            f"Отлично! Вы выбрали тип: {profile.type.value}\n\n"
            f"Ваши доминирующие черты:\n" + 
            "\n".join(f"• {trait.name}: {trait.description}" 
                     for trait in profile.dominant_traits) + 
            "\n\nТеперь давайте начнем ваше путешествие. "
            "Выберите этап, с которого хотите начать:",
            reply_markup=get_journey_stage_keyboard()
        )
        await state.set_state(DiagnosticStates.WAITING_FOR_JOURNEY_STAGE)
    except Exception as e:
        logger.error(f"Error processing psychological type: {e}")
        await callback.message.edit_text(
            "Произошла ошибка. Пожалуйста, попробуйте снова /start_journey"
        )
        await state.clear()

@router.callback_query(DiagnosticStates.WAITING_FOR_JOURNEY_STAGE)
async def process_journey_stage(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора этапа путешествия"""
    try:
        stage = JourneyStageEnum(callback.data)
        data = await state.get_data()
        psychological_type = PsychotypeEnum(data["psychological_type"])
        
        stage_info = JOURNEY_STAGES[stage]
        profile = PSYCHOLOGICAL_TYPES[psychological_type]
        
        # Адаптируем вопросы под психологический тип
        adapted_questions = adapt_questions_to_type(
            stage_info.questions,
            profile
        )
        
        await state.update_data(
            current_stage=stage,
            current_question_index=0,
            adapted_questions=adapted_questions,
            answers={}  # Словарь для хранения ответов
        )
        
        await callback.message.edit_text(
            f"Этап: {stage_info.name}\n\n"
            f"{stage_info.description}\n\n"
            f"Первый вопрос:\n{adapted_questions[0]}",
            reply_markup=get_question_keyboard()
        )
        await state.set_state(DiagnosticStates.answering_questions)
    except Exception as e:
        logger.error(f"Error processing journey stage: {e}")
        await callback.message.edit_text(
            "Произошла ошибка. Пожалуйста, попробуйте снова /start_journey"
        )
        await state.clear()

@router.message(DiagnosticStates.answering_questions)
async def process_answer(message: Message, state: FSMContext):
    """Обработка ответов на вопросы"""
    try:
        data = await state.get_data()
        current_index = data["current_question_index"]
        adapted_questions = data["adapted_questions"]
        answers = data["answers"]
        
        # Сохраняем ответ
        answers[adapted_questions[current_index]] = message.text
        
        if current_index + 1 < len(adapted_questions):
            # Переходим к следующему вопросу
            await state.update_data(
                current_question_index=current_index + 1,
                answers=answers
            )
            await message.answer(
                f"Следующий вопрос:\n{adapted_questions[current_index + 1]}",
                reply_markup=get_question_keyboard()
            )
        else:
            # Завершаем этап и сохраняем результаты
            stage = JourneyStageEnum(data["current_stage"])
            psychological_type = PsychotypeEnum(data["psychological_type"])
            stage_info = JOURNEY_STAGES[stage]
            profile = PSYCHOLOGICAL_TYPES[psychological_type]
            
            # Создаем запись в базе данных
            async with AsyncSession() as session:
                diagnostic_result = DiagnosticResult(
                    user_id=message.from_user.id,
                    psychotype=psychological_type,
                    journey_stage=stage,
                    answers=answers,
                    description=stage_info.description,
                    strengths=profile.dominant_traits,
                    challenges=stage_info.resistance_patterns,
                    emotional_triggers=stage_info.emotional_triggers,
                    logical_patterns=profile.resistance_patterns,
                    current_state=stage_info.psychological_impact,
                    next_steps=adapted_questions,
                    emotional_state=stage_info.emotional_triggers[0] if stage_info.emotional_triggers else None,
                    resistance_points=stage_info.resistance_patterns
                )
                session.add(diagnostic_result)
                await session.commit()
            
            await message.answer(
                f"Отлично! Вы завершили этап '{stage_info.name}'.\n\n"
                "Ваши ответы сохранены и будут использованы для дальнейшего анализа.\n\n"
                "Хотите продолжить путешествие? Выберите следующий этап:",
                reply_markup=get_journey_stage_keyboard()
            )
            await state.set_state(DiagnosticStates.WAITING_FOR_JOURNEY_STAGE)
    except Exception as e:
        logger.error(f"Error processing answer: {e}")
        await message.answer(
            "Произошла ошибка. Пожалуйста, попробуйте снова /start_journey"
        )
        await state.clear()

def adapt_questions_to_type(questions: list, profile: PsychologicalProfile) -> list:
    """Адаптирует вопросы под психологический тип пользователя"""
    adapted_questions = []
    for question in questions:
        # Добавляем эмоциональные триггеры для эмоционального типа
        if profile.type == PsychotypeEnum.EMOTIONAL:
            question = f"Как вы чувствуете себя, когда {question.lower()}"
        # Добавляем практический контекст для практического типа
        elif profile.type == PsychotypeEnum.PRACTICAL:
            question = f"Какие конкретные шаги вы можете сделать, чтобы {question.lower()}"
        # Добавляем аналитический контекст для аналитического типа
        elif profile.type == PsychotypeEnum.ANALYTICAL:
            question = f"Проанализируйте, почему {question.lower()}"
        # Добавляем креативный контекст для интуитивного типа
        elif profile.type == PsychotypeEnum.INTUITIVE:
            question = f"Представьте, что {question.lower()}"
        adapted_questions.append(question)
    return adapted_questions 