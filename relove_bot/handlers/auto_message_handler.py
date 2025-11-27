"""
Обработчик для автоматического написания сообщений.
Анализирует профиль и пишет сообщения на основе состояния.
"""
from aiogram import Router, types
from aiogram.filters import Command

from relove_bot.services.profile_analyzer import get_profile_analyzer
from relove_bot.services.natasha_service import get_natasha_service
from relove_bot.services.prompt_selector import DialogTopic

router = Router()


@router.message(Command("analyze_me"))
async def analyze_profile(message: types.Message):
    """Проанализируй мой профиль и напиши сообщение."""
    try:
        profile_analyzer = get_profile_analyzer()
        natasha_service = get_natasha_service()

        # Получи информацию о пользователе
        user_id = str(message.from_user.id)
        bio = message.from_user.first_name or ""
        
        # Анализируй профиль
        profile_data = profile_analyzer.analyze_profile(
            user_id=user_id,
            bio=bio,
            posts=[],  # В реальном приложении получи из БД
            channel_posts=[],  # В реальном приложении получи из личного канала
            conversation_history=[],  # Получи из истории
        )

        # Проверь, нужно ли писать сообщение
        if not profile_analyzer.should_write_message(user_id):
            await message.answer(
                "Пока нет явных признаков для сообщения. "
                "Напиши мне, что тебя волнует 👇"
            )
            return

        # Сгенерируй сообщение
        generated_message = profile_analyzer.generate_message(user_id, profile_data)

        if generated_message:
            # Отправь сгенерированное сообщение
            await message.answer(generated_message)

            # Получи ответ Наташи
            result = await natasha_service.get_response(
                user_id=user_id,
                message=generated_message
            )

            if result["success"]:
                # Отправь ответ
                from relove_bot.handlers.message_handler import get_predictive_bubbles
                topic = result["topic_enum"].value
                await message.answer(
                    result["response"],
                    reply_markup=get_predictive_bubbles(result["response"], topic)
                )
        else:
            await message.answer("Не смогла сгенерировать сообщение. Напиши сам 👇")

    except Exception as e:
        await message.answer("Ошибка при анализе профиля. Попробуй позже.")


@router.message(Command("profile_state"))
async def show_profile_state(message: types.Message):
    """Покажи анализ моего профиля."""
    try:
        profile_analyzer = get_profile_analyzer()
        user_id = str(message.from_user.id)

        profile_data = profile_analyzer.user_profiles.get(user_id)

        if not profile_data:
            await message.answer(
                "Профиль еще не проанализирован. "
                "Напиши /analyze_me для анализа."
            )
            return

        state = profile_data.get("state", {})

        text = f"""
📊 **Анализ твоего профиля**

😊 **Эмоциональное состояние**: {state.get('emotional_state', 'unknown')}
⚡ **Уровень энергии**: {state.get('energy_level', 'unknown')}

🎯 **Области фокуса**:
"""
        for area in state.get("focus_areas", []):
            text += f"• {area}\n"

        if state.get("challenges"):
            text += "\n⚠️ **Вызовы**:\n"
            for challenge in state.get("challenges", []):
                text += f"• {challenge}\n"

        if state.get("growth_indicators"):
            text += "\n✨ **Признаки роста**:\n"
            for growth in state.get("growth_indicators", []):
                text += f"• {growth}\n"

        await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.message(Command("write_to_me"))
async def write_to_me(message: types.Message):
    """Напиши мне сообщение на основе моего профиля."""
    try:
        profile_analyzer = get_profile_analyzer()
        user_id = str(message.from_user.id)

        # Анализируй профиль
        profile_data = profile_analyzer.analyze_profile(
            user_id=user_id,
            bio=message.from_user.first_name or "",
        )

        # Сгенерируй сообщение
        generated_message = profile_analyzer.generate_message(user_id, profile_data)

        if generated_message:
            await message.answer(generated_message)
        else:
            await message.answer("Напиши мне, что тебя волнует 👇")

    except Exception as e:
        await message.answer("Ошибка при генерации сообщения.")
