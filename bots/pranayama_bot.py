"""
Бот для автоматической обработки и публикации видео практик пранаямы
"""
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import re
from datetime import datetime

from scripts.video_processing.process_zoom_video import VideoProcessor
from scripts.video_processing.process_zoom_selenium import download_zoom_video_selenium

# Загружаем .env
from dotenv import load_dotenv
load_dotenv()

# Конфигурация
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "577682").split(",")]
CHANNEL_ID = -1002366957431  # ID канала @reloverituals
BOT_TOKEN = os.getenv("PRANAYAMA_BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("PRANAYAMA_BOT_TOKEN не найден в .env файле")

router = Router()

class VideoProcessing(StatesGroup):
    waiting_for_choice = State()

# Временное хранилище для обработанных видео
processed_videos = {}

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Приветствие"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Этот бот доступен только администраторам")
        return
    
    await message.answer(
        "👋 Привет! Я бот для обработки видео практик пранаямы.\n\n"
        "Отправь мне Zoom-ссылку, и я:\n"
        "1. Скачаю видео\n"
        "2. Проверю, что это практика пранаямы\n"
        "3. Обработаю (кроп, очистка звука)\n"
        "4. Сгенерирую 3 варианта поста\n"
        "5. Отправлю тебе на выбор\n\n"
        "Просто отправь ссылку!"
    )

@router.message(F.text.regexp(r'https?://.*zoom\.us/rec/'))
async def process_zoom_link(message: Message, state: FSMContext):
    """Обработка Zoom-ссылки"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    zoom_url = message.text.strip()
    
    # Извлекаем пароль если есть
    passcode = None
    passcode_match = re.search(r'(?:код|code|passcode|пароль)[:\s]*([^\s]+)', message.text, re.IGNORECASE)
    if passcode_match:
        passcode = passcode_match.group(1)
    
    status_msg = await message.answer("⏳ Начинаю обработку...\n\n1️⃣ Скачивание видео через Selenium...")
    
    try:
        # Скачивание через Selenium в отдельном потоке
        loop = asyncio.get_event_loop()
        zoom_email = os.getenv("ZOOM_EMAIL")
        zoom_password = os.getenv("ZOOM_PASSWORD")
        
        video_file = await loop.run_in_executor(
            None,
            lambda: download_zoom_video_selenium(
                zoom_url,
                passcode,
                zoom_email=zoom_email,
                zoom_password=zoom_password
            )
        )
        
        if not video_file:
            await status_msg.edit_text(
                "❌ Не удалось скачать видео автоматически.\n\n"
                "Возможные причины:\n"
                "- Требуется авторизация в Zoom\n"
                "- Запись недоступна\n"
                "- Проблема с ChromeDriver\n\n"
                "Скачай видео вручную и отправь файл."
            )
            return
        
        await status_msg.edit_text("⏳ Обработка видео...\n\n2️⃣ Извлечение аудио...")
        
        # Продолжаем обработку
        await process_downloaded_video(message, status_msg, video_file)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка скачивания: {e}\n\nСкачай видео вручную и отправь файл.")

async def process_downloaded_video(message: Message, status_msg: Message, video_path: Path):
    """Общая функция обработки скачанного видео"""
    try:
        video_dir = video_path.parent
        processor = VideoProcessor(output_dir=str(video_dir))
        
        # Извлекаем аудио для транскрибации
        audio_path = processor.extract_audio(video_path)
        
        await status_msg.edit_text("⏳ Обработка видео...\n\n3️⃣ Транскрибация...")
        
        # Транскрибация
        transcript, _ = processor.transcribe_audio(audio_path)
        
        if not transcript:
            await status_msg.edit_text("❌ Не удалось распознать речь в видео")
            return
        
        await status_msg.edit_text("⏳ Обработка видео...\n\n4️⃣ Проверка содержания...")
        
        # Проверяем, что это практика пранаямы
        is_pranayama = await check_if_pranayama(transcript)
        
        if not is_pranayama:
            await status_msg.edit_text(
                "⚠️ Это видео не похоже на практику пранаямы.\n\n"
                f"Распознанный текст:\n{transcript[:500]}...\n\n"
                "Продолжить обработку?"
            )
            # TODO: Добавить кнопки подтверждения
            return
        
        await status_msg.edit_text("⏳ Обработка видео...\n\n5️⃣ Кроп в вертикальный формат...")
        
        # Обработка видео
        cropped = processor.crop_to_vertical(video_path)
        
        await status_msg.edit_text("⏳ Обработка видео...\n\n6️⃣ Очистка звука...")
        
        clean = processor.clean_audio(cropped)
        
        await status_msg.edit_text("⏳ Обработка видео...\n\n7️⃣ Наложение ватермарка...")
        
        watermark_path = Path(__file__).parent.parent / "data/watermark/relove_logo.png"
        final = processor.add_watermark(clean, watermark_image=str(watermark_path))
        
        await status_msg.edit_text("⏳ Обработка видео...\n\n8️⃣ Генерация постов...")
        
        # Генерируем варианты постов
        posts = await generate_post_variants(transcript)
        
        # Сохраняем данные
        video_id = f"video_{datetime.now().timestamp()}"
        processed_videos[video_id] = {
            "video_path": final,
            "transcript": transcript,
            "posts": posts
        }
        
        await status_msg.delete()
        
        # Отправляем варианты постов
        await send_post_variants(message, video_id, posts, final)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка обработки: {e}")

@router.message(F.video | F.document)
async def process_video_file(message: Message, state: FSMContext):
    """Обработка загруженного видео"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    status_msg = await message.answer("⏳ Обработка видео...\n\n1️⃣ Скачивание...")
    
    try:
        # Получаем файл
        bot = message.bot
        
        if message.video:
            file_id = message.video.file_id
            file_name = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        else:
            file_id = message.document.file_id
            file_name = message.document.file_name
        
        file = await bot.get_file(file_id)
        
        # Скачиваем
        video_dir = Path("data/videos")
        video_dir.mkdir(parents=True, exist_ok=True)
        video_path = video_dir / file_name
        
        await bot.download_file(file.file_path, video_path)
        
        await status_msg.edit_text("⏳ Обработка видео...\n\n2️⃣ Извлечение аудио...")
        
        # Обработка через общую функцию
        await process_downloaded_video(message, status_msg, video_path)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")

async def check_if_pranayama(transcript: str) -> bool:
    """Проверяет, является ли видео практикой пранаямы"""
    keywords = [
        "пранаям", "дыхан", "вдох", "выдох", "практик",
        "медитац", "релакс", "энерг", "чакр"
    ]
    
    transcript_lower = transcript.lower()
    matches = sum(1 for keyword in keywords if keyword in transcript_lower)
    
    return matches >= 2

async def generate_post_variants(transcript: str) -> list:
    """Генерирует 3 варианта поста"""
    # TODO: Интеграция с LLM для генерации постов
    # TODO: Получение астрокалендаря
    
    # Заглушка
    variants = [
        {
            "title": "🌟 Практика пранаямы для гармонии",
            "text": "Сегодня особенный день для работы с дыханием. Присоединяйтесь к практике пранаямы, которая поможет вам:\n\n✨ Успокоить ум\n💫 Наполниться энергией\n🌙 Гармонизировать внутреннее состояние\n\nПрактика длится 7 минут. Найдите удобное место и начнем!",
            "hashtags": "#пранаяма #дыхание #медитация #relove"
        },
        {
            "title": "🧘‍♀️ Дыхательная практика дня",
            "text": "По астрокалендарю сегодня благоприятный день для практик с дыханием.\n\nЭта пранаяма поможет:\n• Снять напряжение\n• Улучшить концентрацию\n• Зарядиться энергией\n\nВключайте видео и практикуйте вместе с нами! 🙏",
            "hashtags": "#практика #йога #осознанность #relove"
        },
        {
            "title": "💨 Сила дыхания",
            "text": "Дыхание - это мост между телом и сознанием.\n\nСегодняшняя практика пранаямы:\n→ Балансирует энергию\n→ Очищает каналы\n→ Приводит в состояние покоя\n\nУделите себе 7 минут. Вы это заслужили! ✨",
            "hashtags": "#пранаяма #энергия #практика #relove"
        }
    ]
    
    return variants

async def send_post_variants(message: Message, video_id: str, posts: list, video_path: Path):
    """Отправляет варианты постов с кнопками выбора"""
    await message.answer("✅ Видео обработано!\n\nВыбери вариант поста:")
    
    for i, post in enumerate(posts, 1):
        text = f"**Вариант {i}**\n\n{post['title']}\n\n{post['text']}\n\n{post['hashtags']}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Опубликовать вариант {i}", callback_data=f"publish_{video_id}_{i-1}")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    
    # Отправляем превью видео
    if video_path.exists() and video_path.stat().st_size < 50 * 1024 * 1024:  # < 50MB
        video_file = FSInputFile(video_path)
        await message.answer_video(video_file, caption="Обработанное видео")

@router.callback_query(F.data.startswith("publish_"))
async def publish_post(callback: CallbackQuery):
    """Публикация выбранного варианта"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещен")
        return
    
    _, video_id, variant_idx = callback.data.split("_")
    variant_idx = int(variant_idx)
    
    if video_id not in processed_videos:
        await callback.answer("Видео не найдено")
        return
    
    data = processed_videos[video_id]
    post = data["posts"][variant_idx]
    video_path = data["video_path"]
    
    await callback.message.edit_text("⏳ Публикую в канал...")
    
    try:
        # Публикуем в канал
        bot = callback.bot
        
        caption = f"{post['title']}\n\n{post['text']}\n\n{post['hashtags']}"
        
        video_file = FSInputFile(video_path)
        await bot.send_video(
            chat_id=CHANNEL_ID,
            video=video_file,
            caption=caption
        )
        
        await callback.message.edit_text(
            f"✅ Пост опубликован в канале!\n\n"
            f"Вариант: {variant_idx + 1}\n"
            f"Канал: {CHANNEL_ID}"
        )
        
        # Удаляем из хранилища
        del processed_videos[video_id]
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка публикации: {e}")

async def main():
    """Запуск бота"""
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    print("🤖 Бот запущен!")
    print(f"Admin IDs: {ADMIN_IDS}")
    print(f"Channel ID: {CHANNEL_ID}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
