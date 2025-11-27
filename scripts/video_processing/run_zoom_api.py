"""
Запуск скачивания Zoom через API с готовыми credentials
"""
from zoom_api_download import ZoomAPIDownloader

# Credentials из Zoom OAuth App
ACCOUNT_ID = "fC3gVVJdQKOWDPQbo05aIA"
CLIENT_ID = "QGJQ_02mSbWNDSfMORLTFQ"
CLIENT_SECRET = "yN3E8MCZSgk2phk1yEgfIIiMiKuiSPFM"

zoom_url = "https://us06web.zoom.us/rec/play/Lch7ENL7eu3iPNYzvXGCJ-BKVf1TvkdAS-m8UFbzn62OEwwN7iSMKqwSRV2eR1CjXaLI5WIvyciNyi1L.zDWx3LVOt90iNF2O"

print("=" * 60)
print("Скачивание Zoom записи через API")
print("=" * 60)

try:
    downloader = ZoomAPIDownloader(ACCOUNT_ID, CLIENT_ID, CLIENT_SECRET)
    video_file = downloader.download_from_url(zoom_url)
    
    if video_file:
        print("\n" + "=" * 60)
        print("✓ Скачивание завершено!")
        print(f"Файл: {video_file}")
        print("\nОбработка видео...")
        print("=" * 60)
        
        # Автоматически обрабатываем видео
        from process_zoom_video import VideoProcessor
        
        processor = VideoProcessor()
        
        # Только основные операции без транскрибации (требует whisper)
        print("\n1. Очистка звука...")
        clean_video = processor.clean_audio(video_file)
        
        print("\n2. Наложение ватермарка...")
        final_video = processor.add_watermark(clean_video, "Private Recording")
        
        print("\n" + "=" * 60)
        print("✓ Обработка завершена!")
        print(f"Финальное видео: {final_video}")
        print("=" * 60)
        
    else:
        print("\n✗ Не удалось скачать видео")
        
except Exception as e:
    print(f"\n✗ Ошибка: {e}")
    print("\nПроверь:")
    print("1. Правильность Client ID")
    print("2. Права доступа OAuth приложения (scope: recording:read)")
    print("3. Доступность записи для твоего аккаунта")
