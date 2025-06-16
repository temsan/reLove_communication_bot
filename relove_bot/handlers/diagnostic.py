from typing import Dict, Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..core.knowledge_base import (
    DIAGNOSTIC_QUESTIONS,
    PSYCHOTYPES,
    JOURNEY_STAGES,
    analyze_answers,
    get_recommendation,
    Psychotype,
    HeroJourneyStage
)
from ..db.models import DiagnosticResult, PsychotypeEnum, JourneyStageEnum
from ..db.repository import get_repository
from ..keyboards.diagnostic import get_diagnostic_keyboard
from ..states.diagnostic_states import DiagnosticStates

router = Router()

@router.message(Command("start_diagnostic"))
async def start_diagnostic(message: Message, state: FSMContext):
    """Начало диагностического тестирования"""
    await state.set_state(DiagnosticStates.STARTING_DIAGNOSTICS)
    await state.update_data(current_question=0, answers={})
    
    question = DIAGNOSTIC_QUESTIONS[0]
    await message.answer(
        f"Добро пожаловать в диагностику reLove! 🌟\n\n"
        f"Этот тест поможет определить ваш текущий этап развития и найти свой уникальный путь трансформации.\n\n"
        f"Вопрос {question['id']} из {len(DIAGNOSTIC_QUESTIONS)}:\n"
        f"{question['text']}\n\n"
        f"Ваш ответ поможет нам понять, как вы взаимодействуете с реальностью "
        f"и какие возможности для роста открыты перед вами.",
        reply_markup=get_diagnostic_keyboard(question["options"])
    )
    await state.set_state(DiagnosticStates.ANSWERING)

@router.callback_query(DiagnosticStates.ANSWERING, F.data.startswith("answer_"))
async def process_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос"""
    data = await state.get_data()
    current_question = data["current_question"]
    answers = data["answers"]
    
    # Сохраняем ответ
    answer = callback.data.split("_")[1]
    answers[str(DIAGNOSTIC_QUESTIONS[current_question]["id"])] = answer
    
    # Переходим к следующему вопросу
    current_question += 1
    
    if current_question < len(DIAGNOSTIC_QUESTIONS):
        await state.update_data(current_question=current_question, answers=answers)
        question = DIAGNOSTIC_QUESTIONS[current_question]
        
        # Добавляем контекст к вопросу
        context = ""
        if question.get("emotional_context"):
            context += f"\n{question['emotional_context']}\n"
        if question.get("logical_context"):
            context += f"\n{question['logical_context']}\n"
        
        await callback.message.edit_text(
            f"Вопрос {question['id']} из {len(DIAGNOSTIC_QUESTIONS)}:\n"
            f"{question['text']}\n\n"
            f"{context}",
            reply_markup=get_diagnostic_keyboard(question["options"])
        )
    else:
        # Тест завершен
        await state.set_state(DiagnosticStates.COMPLETED)
        await state.update_data(answers=answers)
        
        # Рассчитываем результаты
        psychotype, journey_stage = analyze_answers(answers)
        recommendation = get_recommendation(psychotype, journey_stage)
        
        # Получаем описания
        psychotype_desc = PSYCHOTYPES[psychotype]
        journey_desc = JOURNEY_STAGES[journey_stage]
        
        # Формируем результат
        result_text = (
            f"🌟 *Результаты вашей диагностики:*\n\n"
            f"🎯 *Психотип:* {psychotype_desc.name}\n"
            f"{psychotype_desc.description}\n\n"
            f"💫 *Ваши сильные стороны:*\n"
            f"{chr(10).join('• ' + s for s in psychotype_desc.strengths)}\n\n"
            f"🌱 *Области для роста:*\n"
            f"{chr(10).join('• ' + c for c in psychotype_desc.challenges)}\n\n"
            f"🎭 *Эмоциональные триггеры для работы:*\n"
            f"{chr(10).join('• ' + t for t in psychotype_desc.emotional_triggers)}\n\n"
            f"🧠 *Логические паттерны для трансформации:*\n"
            f"{chr(10).join('• ' + p for p in psychotype_desc.logical_patterns)}\n\n"
            f"🌅 *Этап пути:* {journey_desc.name}\n"
            f"{journey_desc.description}\n\n"
            f"💫 *Текущее эмоциональное состояние:*\n"
            f"{journey_desc.emotional_state}\n\n"
            f"🎯 *Точки сопротивления для работы:*\n"
            f"{chr(10).join('• ' + r for r in journey_desc.resistance_points)}\n\n"
            f"📚 *Рекомендуемый поток:* {recommendation['stream']}\n"
            f"{recommendation['description']}\n\n"
            f"Для более глубокой работы над собой и получения персональных рекомендаций, "
            f"присоединяйтесь к нашим потокам reLove! 🌟\n\n"
            f"Каждый поток — это уникальное пространство для трансформации, "
            f"где вы сможете:\n"
            f"• Исследовать новые грани реальности\n"
            f"• Работать с эмоциональными блоками\n"
            f"• Развивать осознанность и интуицию\n"
            f"• Интегрировать духовный опыт в повседневную жизнь\n"
            f"• Найти поддержку единомышленников"
        )
        
        # Сохраняем результаты в базу данных
        repo = get_repository()
        diagnostic_result = DiagnosticResult(
            user_id=callback.from_user.id,
            psychotype=PsychotypeEnum(psychotype.value),
            journey_stage=JourneyStageEnum(journey_stage.value),
            answers=answers,
            description=psychotype_desc.description,
            strengths=psychotype_desc.strengths,
            challenges=psychotype_desc.challenges,
            emotional_triggers=psychotype_desc.emotional_triggers,
            logical_patterns=psychotype_desc.logical_patterns,
            current_state=journey_desc.current_state,
            next_steps=journey_desc.next_steps,
            emotional_state=journey_desc.emotional_state,
            resistance_points=journey_desc.resistance_points,
            recommended_stream=recommendation['stream'],
            stream_description=recommendation['description']
        )
        await repo.create(diagnostic_result)
        
        await callback.message.edit_text(result_text)
        await state.clear()

@router.message(DiagnosticStates.ANSWERING)
async def handle_invalid_answer(message: Message):
    """Обработка некорректного ответа"""
    await message.answer(
        "Пожалуйста, выберите один из предложенных вариантов ответа, "
        "используя кнопки под вопросом."
    ) 