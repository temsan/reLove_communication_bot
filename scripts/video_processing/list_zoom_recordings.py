"""
Список всех доступных Zoom записей
"""
from zoom_api_download import ZoomAPIDownloader
from datetime import datetime, timedelta

# Credentials
ACCOUNT_ID = "fC3gVVJdQKOWDPQbo05aIA"
CLIENT_ID = "QGJQ_02mSbWNDSfMORLTFQ"
CLIENT_SECRET = "yN3E8MCZSgk2phk1yEgfIIiMiKuiSPFM"

print("=" * 60)
print("Список Zoom записей")
print("=" * 60)

try:
    downloader = ZoomAPIDownloader(ACCOUNT_ID, CLIENT_ID, CLIENT_SECRET)
    
    # Получаем записи за последние 30 дней
    from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    to_date = datetime.now().strftime('%Y-%m-%d')
    
    recordings = downloader.list_user_recordings(from_date=from_date, to_date=to_date)
    
    if recordings:
        print("\nДоступные записи:")
        for i, meeting in enumerate(recordings, 1):
            print(f"\n{i}. {meeting.get('topic', 'Без названия')}")
            print(f"   Дата: {meeting.get('start_time', 'N/A')}")
            print(f"   ID: {meeting.get('id', 'N/A')}")
            print(f"   Длительность: {meeting.get('duration', 0)} мин")
            
            files = meeting.get('recording_files', [])
            for file in files:
                file_type = file.get('file_type')
                size_mb = file.get('file_size', 0) / 1024 / 1024
                print(f"   - {file_type}: {size_mb:.1f} MB")
        
        # Предлагаем скачать
        choice = input("\nВведи номер записи для скачивания (или Enter для выхода): ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(recordings):
                meeting = recordings[idx]
                files = meeting.get('recording_files', [])
                
                for file in files:
                    if file.get('file_type') == 'MP4':
                        download_url = file.get('download_url')
                        if download_url:
                            print(f"\nСкачивание: {meeting.get('topic')}...")
                            video_file = downloader.download_recording(download_url)
                            
                            if video_file:
                                print(f"\n✓ Видео скачано: {video_file}")
                                
                                # Обрабатываем
                                process = input("\nОбработать видео (кроп + ватермарк)? (y/n): ").strip().lower()
                                
                                if process == 'y':
                                    from process_zoom_video import VideoProcessor
                                    
                                    processor = VideoProcessor()
                                    
                                    print("\n1. Кроп в вертикальный формат...")
                                    cropped = processor.crop_to_vertical(video_file)
                                    
                                    print("\n2. Очистка звука...")
                                    clean = processor.clean_audio(cropped)
                                    
                                    print("\n3. Наложение ватермарка...")
                                    final = processor.add_watermark(clean, "Private")
                                    
                                    print(f"\n✓ Готово: {final}")
                            break
    else:
        print("\nЗаписей не найдено")
        
except Exception as e:
    print(f"\n✗ Ошибка: {e}")
