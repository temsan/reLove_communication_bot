"""
Попытка скачать Zoom share-ссылку через API
"""
from zoom_api_download import ZoomAPIDownloader
import re

# Credentials
ACCOUNT_ID = "fC3gVVJdQKOWDPQbo05aIA"
CLIENT_ID = "QGJQ_02mSbWNDSfMORLTFQ"
CLIENT_SECRET = "yN3E8MCZSgk2phk1yEgfIIiMiKuiSPFM"

share_urls = [
    "https://us06web.zoom.us/rec/share/8XJFkKaQ5_lH32KOhX-xzN7TOe9wTb3IHo9k3dLXSuSFA7G9sWZnsmNr-60ne8Vd.Jc0yHUzjmtgZs9Zl",
    "https://us06web.zoom.us/rec/share/4Fsn5HhQ9hCV1_fcYxXmt2K1pdN1rAM1vTg_l_Zrencd603ns4crRKO8AeKMPpdK.I6qLpkl1nvXF8UnI"
]

def extract_share_id(url):
    """Извлекает ID из share-ссылки"""
    match = re.search(r'/rec/share/([^?]+)', url)
    if match:
        return match.group(1)
    return None

print("=" * 60)
print("Попытка скачать share-ссылки через API")
print("=" * 60)

try:
    downloader = ZoomAPIDownloader(ACCOUNT_ID, CLIENT_ID, CLIENT_SECRET)
    
    # Получаем все доступные записи
    print("\nПолучение списка всех записей...")
    recordings = downloader.list_user_recordings()
    
    if not recordings:
        print("\n✗ Записей не найдено через API")
        print("\nShare-ссылки требуют:")
        print("1. Скачивание вручную через браузер")
        print("2. Или доступ к аккаунту владельца записи")
        print("\nДля скачивания вручную:")
        for i, url in enumerate(share_urls, 1):
            print(f"\n{i}. Открой: {url}")
            print(f"   Скачай видео")
        
        print("\nЗатем обработай:")
        print("python scripts/video_processing/process_local_video.py путь\\к\\видео.mp4")
    else:
        print(f"\n✓ Найдено записей: {len(recordings)}")
        
        # Пробуем найти совпадения
        share_ids = [extract_share_id(url) for url in share_urls]
        
        print("\nShare IDs из ссылок:")
        for sid in share_ids:
            print(f"  - {sid}")
        
        print("\nДоступные записи:")
        for i, meeting in enumerate(recordings, 1):
            print(f"\n{i}. {meeting.get('topic', 'Без названия')}")
            print(f"   ID: {meeting.get('id')}")
            print(f"   UUID: {meeting.get('uuid', 'N/A')}")
            print(f"   Дата: {meeting.get('start_time')}")
        
        # Предлагаем скачать любую доступную
        choice = input("\nВведи номер записи для скачивания: ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(recordings):
                meeting = recordings[idx]
                files = meeting.get('recording_files', [])
                
                for file in files:
                    if file.get('file_type') == 'MP4':
                        download_url = file.get('download_url')
                        if download_url:
                            video_file = downloader.download_recording(download_url)
                            
                            if video_file:
                                print(f"\n✓ Видео скачано: {video_file}")
                                
                                # Автоматически обрабатываем
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
        
except Exception as e:
    print(f"\n✗ Ошибка: {e}")
    print("\nShare-ссылки не доступны через API")
    print("Скачай видео вручную через браузер")
