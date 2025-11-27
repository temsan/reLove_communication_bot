"""
Запуск обработки Zoom видео
"""
from process_zoom_video import VideoProcessor

if __name__ == "__main__":
    processor = VideoProcessor()
    
    zoom_url = "https://us06web.zoom.us/rec/play/Lch7ENL7eu3iPNYzvXGCJ-BKVf1TvkdAS-m8UFbzn62OEwwN7iSMKqwSRV2eR1CjXaLI5WIvyciNyi1L.zDWx3LVOt90iNF2O?eagerLoadZvaPages=sidemenu.billing.plan_management&accessLevel=meeting&canPlayFromShare=true&from=share_recording_detail&continueMode=true&componentName=rec-play&originRequestUrl=https%3A%2F%2Fus06web.zoom.us%2Frec%2Fshare%2Fl2gqtAe5vJNDIKeITgSHdYRY0S7VCYdl1niakvgZ4jtn6udMIPHOQGAVCalX8GK4.oy18D3f8RMaCuNB3"
    
    try:
        results = processor.process_full_pipeline(
            url=zoom_url,
            watermark_text="Private Recording"
        )
        
        print("\n✓ Обработка завершена успешно!")
        print(f"\nФинальное видео: {results['final_video']}")
        if results.get('topic_analysis'):
            print(f"\nТоп-5 ключевых слов:")
            for word, count in results['topic_analysis']['top_keywords'][:5]:
                print(f"  - {word}: {count}")
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        print("\nПроверь:")
        print("1. Установлены ли зависимости: pip install requests openai-whisper")
        print("2. Установлен ли ffmpeg")
        print("3. Доступна ли ссылка на видео")
