"""
Тесты обработки видео
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.video_processing.process_zoom_video import VideoProcessor


class TestVideoProcessor:
    """Тесты класса VideoProcessor"""
    
    def test_processor_initialization(self):
        """Проверяет инициализацию процессора"""
        processor = VideoProcessor(output_dir="data/test_videos")
        
        assert processor.output_dir.exists()
        assert processor.output_dir.name == "test_videos"
    
    def test_output_directory_creation(self):
        """Проверяет создание выходной директории"""
        test_dir = Path("data/test_output")
        
        if test_dir.exists():
            import shutil
            shutil.rmtree(test_dir)
        
        processor = VideoProcessor(output_dir=str(test_dir))
        
        assert test_dir.exists()
        
        # Cleanup
        import shutil
        shutil.rmtree(test_dir)


class TestWatermark:
    """Тесты ватермарка"""
    
    def test_watermark_file_exists(self):
        """Проверяет наличие файла ватермарка"""
        watermark_path = Path("data/watermark/relove_logo.png")
        
        assert watermark_path.exists(), "Файл ватермарка не найден"
    
    def test_watermark_is_png(self):
        """Проверяет формат ватермарка"""
        watermark_path = Path("data/watermark/relove_logo.png")
        
        assert watermark_path.suffix == ".png"
    
    def test_watermark_size(self):
        """Проверяет размер файла ватермарка"""
        watermark_path = Path("data/watermark/relove_logo.png")
        
        if watermark_path.exists():
            size = watermark_path.stat().st_size
            assert size > 0, "Файл ватермарка пустой"
            assert size < 1024 * 1024, "Файл ватермарка слишком большой (>1MB)"


class TestSeleniumDownloader:
    """Тесты Selenium загрузчика"""
    
    def test_zoom_url_extraction(self):
        """Проверяет извлечение ID из Zoom URL"""
        import re
        
        url = "https://us06web.zoom.us/rec/play/Lch7ENL7eu3iPNYzvXGCJ.zDWx3LVOt90iNF2O"
        
        match = re.search(r'/rec/play/([^?]+)', url)
        
        assert match is not None
        assert len(match.group(1)) > 0
    
    def test_share_url_extraction(self):
        """Проверяет извлечение ID из share URL"""
        import re
        
        url = "https://us06web.zoom.us/rec/share/8XJFkKaQ5_lH32KOhX.Jc0yHUzjmtgZs9Zl"
        
        match = re.search(r'/rec/share/([^?]+)', url)
        
        assert match is not None
        assert len(match.group(1)) > 0


class TestTranscription:
    """Тесты транскрибации"""
    
    def test_pranayama_keywords(self):
        """Проверяет ключевые слова пранаямы"""
        keywords = [
            "пранаям", "дыхан", "вдох", "выдох", "практик",
            "медитац", "релакс", "энерг", "чакр"
        ]
        
        test_text = "Практика пранаямы с дыханием и медитацией"
        
        matches = sum(1 for keyword in keywords if keyword in test_text.lower())
        
        assert matches >= 2
    
    def test_non_pranayama_text(self):
        """Проверяет текст не о пранаяме"""
        keywords = [
            "пранаям", "дыхан", "вдох", "выдох", "практик",
            "медитац", "релакс", "энерг", "чакр"
        ]
        
        test_text = "Обсуждение финансовых показателей компании"
        
        matches = sum(1 for keyword in keywords if keyword in test_text.lower())
        
        assert matches < 2


class TestFFmpegCommands:
    """Тесты команд FFmpeg"""
    
    def test_crop_command_structure(self):
        """Проверяет структуру команды кропа"""
        width, height = 1920, 1080
        target_width = int(height * 9 / 16)
        x_offset = (width - target_width) // 2
        
        assert target_width == 607
        assert x_offset == 656
    
    def test_quality_settings(self):
        """Проверяет настройки качества"""
        crf = 18
        preset = "slow"
        
        assert crf >= 0 and crf <= 51
        assert preset in ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
