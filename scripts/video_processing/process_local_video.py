"""
Обработка локального видео: кроп в вертикальный формат, очистка звука, ватермарк
"""
from process_zoom_video import VideoProcessor
from pathlib import Path
import sys

def process_video(video_path, watermark="Private"):
    """Обрабатывает локальное видео"""
    video_file = Path(video_path)
    
    if not video_file.exists():
        print(f"✗ Файл не найден: {video_path}")
        return
    
    print("=" * 60)
    print(f"Обработка: {video_file.name}")
    print("=" * 60)
    
    processor = VideoProcessor(output_dir=video_file.parent)
    
    try:
        # 1. Кроп в вертикальный формат (9:16)
        print("\n1. Кроп в вертикальный формат (убираем черные полосы)...")
        cropped = processor.crop_to_vertical(video_file)
        
        # 2. Очистка звука
        print("\n2. Очистка звука...")
        clean = processor.clean_audio(cropped)
        
        # 3. Наложение ватермарка
        print(f"\n3. Наложение ватермарка '{watermark}'...")
        final = processor.add_watermark(clean, watermark)
        
        print("\n" + "=" * 60)
        print("✓ Обработка завершена!")
        print(f"Финальное видео: {final}")
        print("=" * 60)
        
        # Опционально: транскрибация
        transcribe = input("\nТранскрибировать аудио? (требует whisper) (y/n): ").strip().lower()
        
        if transcribe == 'y':
            print("\n4. Извлечение аудио...")
            audio = processor.extract_audio(final)
            
            print("\n5. Транскрибация...")
            transcript, transcript_path = processor.transcribe_audio(audio)
            
            if transcript:
                print(f"\n✓ Транскрипт сохранен: {transcript_path}")
                
                # Анализ темы
                analysis = processor.analyze_topic(transcript)
                print(f"\nТоп-5 ключевых слов:")
                for word, count in analysis['top_keywords'][:5]:
                    print(f"  - {word}: {count}")
        
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        watermark = sys.argv[2] if len(sys.argv) > 2 else "Private"
    else:
        video_path = input("Путь к видео файлу: ").strip()
        watermark = input("Текст ватермарка (Enter = 'Private'): ").strip() or "Private"
    
    process_video(video_path, watermark)
