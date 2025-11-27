"""
Тесты для бота обработки видео пранаямы
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from bots.pranayama_bot import (
    check_if_pranayama,
    generate_post_variants,
    processed_videos
)


class TestPranayamaDetection:
    """Тесты проверки содержания видео"""
    
    def test_pranayama_keywords_detected(self):
        """Проверяет распознавание практики пранаямы"""
        transcript = "Сегодня мы будем практиковать дыхательную технику пранаямы. Делаем глубокий вдох и медленный выдох."
        
        result = asyncio.run(check_if_pranayama(transcript))
        
        assert result is True
    
    def test_non_pranayama_content(self):
        """Проверяет отклонение не-пранаямы"""
        transcript = "Сегодня мы обсудим финансовые показатели компании и стратегию развития бизнеса."
        
        result = asyncio.run(check_if_pranayama(transcript))
        
        assert result is False
    
    def test_partial_match(self):
        """Проверяет частичное совпадение ключевых слов"""
        transcript = "Практика медитации с элементами дыхания"
        
        result = asyncio.run(check_if_pranayama(transcript))
        
        assert result is True


class TestPostGeneration:
    """Тесты генерации постов"""
    
    @pytest.mark.asyncio
    async def test_generate_three_variants(self):
        """Проверяет генерацию 3 вариантов постов"""
        transcript = "Практика пранаямы для начинающих"
        
        posts = await generate_post_variants(transcript)
        
        assert len(posts) == 3
        assert all('title' in post for post in posts)
        assert all('text' in post for post in posts)
        assert all('hashtags' in post for post in posts)
    
    @pytest.mark.asyncio
    async def test_post_structure(self):
        """Проверяет структуру сгенерированного поста"""
        transcript = "Дыхательная практика"
        
        posts = await generate_post_variants(transcript)
        post = posts[0]
        
        assert isinstance(post['title'], str)
        assert isinstance(post['text'], str)
        assert isinstance(post['hashtags'], str)
        assert len(post['title']) > 0
        assert len(post['text']) > 0
        assert '#' in post['hashtags']


class TestVideoProcessing:
    """Тесты обработки видео"""
    
    @pytest.mark.skipif(not Path("data/videos").exists(), reason="Нет тестовых видео")
    def test_video_directory_creation(self):
        """Проверяет создание директории для видео"""
        from scripts.video_processing.process_zoom_video import VideoProcessor
        
        processor = VideoProcessor(output_dir="data/test_videos")
        
        assert Path("data/test_videos").exists()
    
    def test_watermark_path_exists(self):
        """Проверяет наличие файла ватермарка"""
        watermark_path = Path("data/watermark/relove_logo.png")
        
        assert watermark_path.exists(), "Ватермарк не найден"


class TestBotConfiguration:
    """Тесты конфигурации бота"""
    
    def test_admin_ids_loaded(self):
        """Проверяет загрузку ID администраторов"""
        from bots.pranayama_bot import ADMIN_IDS
        
        assert isinstance(ADMIN_IDS, list)
        assert len(ADMIN_IDS) > 0
        assert all(isinstance(id, int) for id in ADMIN_IDS)
    
    def test_channel_id_configured(self):
        """Проверяет настройку ID канала"""
        from bots.pranayama_bot import CHANNEL_ID
        
        assert isinstance(CHANNEL_ID, int)
        assert CHANNEL_ID < 0  # ID каналов отрицательные
    
    def test_bot_token_loaded(self):
        """Проверяет загрузку токена бота"""
        from bots.pranayama_bot import BOT_TOKEN
        
        assert BOT_TOKEN is not None
        assert len(BOT_TOKEN) > 0


class TestZoomIntegration:
    """Тесты интеграции с Zoom"""
    
    def test_zoom_url_pattern(self):
        """Проверяет распознавание Zoom-ссылок"""
        import re
        
        pattern = r'https?://.*zoom\.us/rec/'
        
        valid_urls = [
            "https://us06web.zoom.us/rec/play/abc123",
            "https://zoom.us/rec/share/xyz789"
        ]
        
        invalid_urls = [
            "https://youtube.com/watch?v=123",
            "https://example.com"
        ]
        
        for url in valid_urls:
            assert re.search(pattern, url), f"Не распознана валидная ссылка: {url}"
        
        for url in invalid_urls:
            assert not re.search(pattern, url), f"Ложное срабатывание на: {url}"
    
    def test_passcode_extraction(self):
        """Проверяет извлечение пароля из текста"""
        import re
        
        text = "Ссылка на запись: https://zoom.us/rec/123 код: ^Ufw4B8k"
        
        passcode_match = re.search(r'(?:код|code|passcode|пароль)[:\s]*([^\s]+)', text, re.IGNORECASE)
        
        assert passcode_match is not None
        assert passcode_match.group(1) == "^Ufw4B8k"


@pytest.fixture
def mock_message():
    """Фикстура для мок-сообщения"""
    message = Mock()
    message.from_user.id = 577682
    message.text = "https://zoom.us/rec/test"
    message.answer = AsyncMock()
    return message


@pytest.fixture
def mock_bot():
    """Фикстура для мок-бота"""
    bot = Mock()
    bot.get_file = AsyncMock()
    bot.download_file = AsyncMock()
    bot.send_video = AsyncMock()
    return bot


class TestBotHandlers:
    """Тесты обработчиков бота"""
    
    @pytest.mark.asyncio
    async def test_start_command_for_admin(self, mock_message):
        """Проверяет команду /start для админа"""
        from bots.pranayama_bot import cmd_start
        
        await cmd_start(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Привет" in call_args
    
    @pytest.mark.asyncio
    async def test_start_command_for_non_admin(self, mock_message):
        """Проверяет команду /start для не-админа"""
        from bots.pranayama_bot import cmd_start
        
        mock_message.from_user.id = 999999  # Не админ
        
        await cmd_start(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "администратор" in call_args.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
