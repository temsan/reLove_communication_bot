"""
Скрипт для обработки видео: скачивание, очистка звука, наложение ватермарка, транскрибация
"""
import os
import re
import requests
from pathlib import Path
import subprocess
import json
from datetime import datetime
from bs4 import BeautifulSoup

class VideoProcessor:
    def __init__(self, output_dir="data/videos"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def extract_video_url_from_zoom(self, page_url):
        """Извлекает прямую ссылку на видео из Zoom страницы"""
        print(f"Получение страницы: {page_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(page_url, headers=headers)
        response.raise_for_status()
        
        # Ищем ссылку на видео в HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Вариант 1: ищем в тегах video/source
        video_tag = soup.find('video')
        if video_tag:
            source = video_tag.find('source')
            if source and source.get('src'):
                return source['src']
        
        # Вариант 2: ищем в JavaScript переменных
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Ищем viewMp4Url или downloadUrl
                match = re.search(r'"viewMp4Url"\s*:\s*"([^"]+)"', script.string)
                if match:
                    return match.group(1).replace('\\/', '/')
                
                match = re.search(r'"downloadUrl"\s*:\s*"([^"]+)"', script.string)
                if match:
                    return match.group(1).replace('\\/', '/')
                
                # Ищем любые .mp4 ссылки
                match = re.search(r'https?://[^"\']+\.mp4[^"\']*', script.string)
                if match:
                    return match.group(0).replace('\\/', '/')
        
        # Вариант 3: ищем data атрибуты
        elements = soup.find_all(attrs={'data-video-url': True})
        if elements:
            return elements[0]['data-video-url']
        
        raise Exception("Не удалось найти ссылку на видео на странице")
    
    def download_video(self, url, filename=None):
        """Скачивает видео по URL"""
        if filename is None:
            filename = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        output_path = self.output_dir / filename
        
        # Если это Zoom страница, извлекаем прямую ссылку
        if 'zoom.us' in url and '/rec/play' in url:
            print("Обнаружена Zoom страница, извлекаем прямую ссылку...")
            url = self.extract_video_url_from_zoom(url)
            print(f"Найдена прямая ссылка: {url[:100]}...")
        
        print(f"Скачивание видео...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\rПрогресс: {percent:.1f}%", end='')
        
        print(f"\nВидео сохранено: {output_path}")
        return output_path
    
    def clean_audio(self, input_path, output_path=None):
        """Очистка звука с помощью ffmpeg"""
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_clean{input_path.suffix}"
        
        print(f"Очистка звука: {input_path}")
        
        # Удаление шума и нормализация громкости
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-af', 'highpass=f=200,lowpass=f=3000,volume=1.5',
            '-c:v', 'copy',
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True)
        print(f"Звук очищен: {output_path}")
        return output_path
    
    def crop_to_vertical(self, input_path, output_path=None, aspect_ratio="9:16"):
        """Кроп видео в вертикальный формат (убирает черные полосы)"""
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_vertical{input_path.suffix}"
        
        print(f"Кроп в вертикальный формат: {input_path}")
        
        # Получаем размеры видео
        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'json',
            str(input_path)
        ]
        
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        info = json.loads(result.stdout)
        
        width = info['streams'][0]['width']
        height = info['streams'][0]['height']
        
        print(f"Исходный размер: {width}x{height}")
        
        # Вычисляем размеры для 9:16
        if aspect_ratio == "9:16":
            target_width = int(height * 9 / 16)
            target_height = height
        else:
            target_width = width
            target_height = int(width * 16 / 9)
        
        # Центрируем кроп
        x_offset = (width - target_width) // 2
        
        print(f"Кроп: {target_width}x{target_height} (смещение x={x_offset})")
        
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-vf', f'crop={target_width}:{target_height}:{x_offset}:0',
            '-c:v', 'libx264', '-crf', '18', '-preset', 'slow',
            '-c:a', 'copy',
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True)
        print(f"Видео обрезано: {output_path}")
        return output_path
    
    def add_watermark(self, input_path, watermark_image=None, output_path=None):
        """Наложение ватермарка (изображение или текст)"""
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_watermarked{input_path.suffix}"
        
        print(f"Наложение ватермарка: {input_path}")
        
        # Если не указано изображение, используем логотип по умолчанию
        if watermark_image is None:
            watermark_image = Path(__file__).parent.parent.parent / "data/watermark/relove_logo.png"
        
        watermark_path = Path(watermark_image)
        
        if watermark_path.exists() and watermark_path.suffix in ['.png', '.svg']:
            # Конвертируем SVG в PNG если нужно
            if watermark_path.suffix == '.svg':
                png_path = watermark_path.with_suffix('.png')
                if not png_path.exists():
                    # Конвертация SVG -> PNG через ffmpeg
                    subprocess.run([
                        'ffmpeg', '-i', str(watermark_path),
                        '-vf', 'scale=200:200',
                        str(png_path)
                    ], check=True)
                watermark_path = png_path
            
            # Накладываем изображение в правый нижний угол
            cmd = [
                'ffmpeg', '-i', str(input_path),
                '-i', str(watermark_path),
                '-filter_complex', '[1:v]scale=100:-1[wm];[0:v][wm]overlay=W-w-10:H-h-10',
                '-c:v', 'libx264', '-crf', '18', '-preset', 'slow',
                '-c:a', 'copy',
                str(output_path)
            ]
        else:
            # Текстовый ватермарк как fallback
            cmd = [
                'ffmpeg', '-i', str(input_path),
                '-vf', "drawtext=text='reLove':fontsize=24:fontcolor=white@0.7:x=10:y=10",
                '-c:v', 'libx264', '-crf', '18', '-preset', 'slow',
                '-c:a', 'copy',
                str(output_path)
            ]
        
        subprocess.run(cmd, check=True)
        print(f"Ватермарк добавлен: {output_path}")
        return output_path
    
    def extract_audio(self, input_path, output_path=None):
        """Извлечение аудио из видео"""
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}.wav"
        
        print(f"Извлечение аудио: {input_path}")
        
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True)
        print(f"Аудио извлечено: {output_path}")
        return output_path
    
    def transcribe_audio(self, audio_path):
        """Транскрибация аудио (требует whisper)"""
        try:
            import whisper
            
            print(f"Транскрибация: {audio_path}")
            model = whisper.load_model("base")
            result = model.transcribe(str(audio_path), language="ru")
            
            transcript_path = audio_path.parent / f"{audio_path.stem}_transcript.txt"
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(result["text"])
            
            print(f"Транскрипт сохранен: {transcript_path}")
            return result["text"], transcript_path
        except ImportError:
            print("Whisper не установлен. Установите: pip install openai-whisper")
            return None, None
    
    def analyze_topic(self, transcript):
        """Анализ темы по транскрипту"""
        if not transcript:
            return "Не удалось определить тему"
        
        # Простой анализ ключевых слов
        keywords = transcript.lower().split()
        word_freq = {}
        for word in keywords:
            if len(word) > 4:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "transcript_length": len(transcript),
            "word_count": len(keywords),
            "top_keywords": top_words
        }
    
    def process_full_pipeline(self, url, watermark_text="Confidential", crop_vertical=True):
        """Полный пайплайн обработки"""
        print("=" * 50)
        print("Начало обработки видео")
        print("=" * 50)
        
        # 1. Скачивание
        video_path = self.download_video(url)
        
        # 2. Кроп в вертикальный формат
        if crop_vertical:
            video_path = self.crop_to_vertical(video_path)
        
        # 3. Очистка звука
        clean_video = self.clean_audio(video_path)
        
        # 4. Наложение ватермарка
        final_video = self.add_watermark(clean_video, watermark_text)
        
        # 5. Извлечение аудио
        audio_path = self.extract_audio(final_video)
        
        # 5. Транскрибация
        transcript, transcript_path = self.transcribe_audio(audio_path)
        
        # 6. Анализ темы
        if transcript:
            topic_analysis = self.analyze_topic(transcript)
            
            analysis_path = self.output_dir / f"{video_path.stem}_analysis.json"
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(topic_analysis, f, ensure_ascii=False, indent=2)
            
            print(f"\nАнализ темы сохранен: {analysis_path}")
            print(f"Топ ключевых слов: {topic_analysis['top_keywords'][:5]}")
        
        print("\n" + "=" * 50)
        print("Обработка завершена!")
        print(f"Финальное видео: {final_video}")
        print("=" * 50)
        
        return {
            "original": video_path,
            "final_video": final_video,
            "audio": audio_path,
            "transcript": transcript_path,
            "topic_analysis": topic_analysis if transcript else None
        }


if __name__ == "__main__":
    # Пример использования
    processor = VideoProcessor()
    
    # Замени на свою ссылку
    zoom_url = "YOUR_ZOOM_VIDEO_URL"
    
    results = processor.process_full_pipeline(
        url=zoom_url,
        watermark_text="Private Recording"
    )
    
    print("\nРезультаты:")
    for key, value in results.items():
        print(f"{key}: {value}")
