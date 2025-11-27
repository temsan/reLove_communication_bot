"""
Скачивание Zoom записей через API с OAuth
"""
import requests
import time
from pathlib import Path
from datetime import datetime
import json

class ZoomAPIDownloader:
    def __init__(self, account_id, client_id, client_secret):
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = 0
        
    def get_access_token(self):
        """Получение OAuth токена"""
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
        
        print("Получение OAuth токена...")
        
        url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={self.account_id}"
        
        response = requests.post(
            url,
            auth=(self.client_id, self.client_secret),
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data['access_token']
            self.token_expires_at = time.time() + data['expires_in'] - 60
            print("✓ Токен получен")
            return self.access_token
        else:
            raise Exception(f"Ошибка получения токена: {response.status_code} - {response.text}")
    
    def extract_meeting_id(self, url):
        """Извлекает meeting ID из URL"""
        import re
        match = re.search(r'/rec/play/([^?]+)', url)
        if match:
            return match.group(1)
        return None
    
    def get_recording_info(self, meeting_id):
        """Получает информацию о записи"""
        token = self.get_access_token()
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        # Пробуем разные endpoints
        endpoints = [
            f"https://api.zoom.us/v2/meetings/{meeting_id}/recordings",
            f"https://api.zoom.us/v2/recordings/{meeting_id}"
        ]
        
        for endpoint in endpoints:
            print(f"Запрос к API: {endpoint}")
            response = requests.get(endpoint, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                continue
            else:
                print(f"Ошибка: {response.status_code} - {response.text}")
        
        return None
    
    def list_user_recordings(self, user_id='me', from_date=None, to_date=None):
        """Список всех записей пользователя"""
        token = self.get_access_token()
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        params = {}
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        url = f"https://api.zoom.us/v2/users/{user_id}/recordings"
        
        print(f"Получение списка записей...")
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            meetings = data.get('meetings', [])
            print(f"✓ Найдено записей: {len(meetings)}")
            return meetings
        else:
            raise Exception(f"Ошибка: {response.status_code} - {response.text}")
    
    def download_recording(self, download_url, output_dir="data/videos"):
        """Скачивает запись по прямой ссылке"""
        token = self.get_access_token()
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        filename = output_path / f"zoom_recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        print(f"Скачивание: {download_url[:80]}...")
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        response = requests.get(download_url, headers=headers, stream=True)
        
        if response.status_code == 200:
            total = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(f"\rПрогресс: {downloaded/total*100:.1f}%", end='')
            
            print(f"\n✓ Видео сохранено: {filename}")
            return filename
        else:
            raise Exception(f"Ошибка скачивания: {response.status_code}")
    
    def download_from_url(self, zoom_url, output_dir="data/videos"):
        """Скачивает запись по URL страницы Zoom"""
        meeting_id = self.extract_meeting_id(zoom_url)
        
        if not meeting_id:
            print("✗ Не удалось извлечь meeting ID из URL")
            print("\nПопробуем получить список всех записей...")
            
            # Получаем список записей
            recordings = self.list_user_recordings()
            
            if recordings:
                print("\nДоступные записи:")
                for i, meeting in enumerate(recordings, 1):
                    print(f"\n{i}. {meeting.get('topic', 'Без названия')}")
                    print(f"   Дата: {meeting.get('start_time', 'N/A')}")
                    print(f"   ID: {meeting.get('id', 'N/A')}")
                    
                    files = meeting.get('recording_files', [])
                    for file in files:
                        if file.get('file_type') == 'MP4':
                            print(f"   Размер: {file.get('file_size', 0) / 1024 / 1024:.1f} MB")
                
                # Скачиваем первую найденную MP4
                for meeting in recordings:
                    files = meeting.get('recording_files', [])
                    for file in files:
                        if file.get('file_type') == 'MP4':
                            download_url = file.get('download_url')
                            if download_url:
                                return self.download_recording(download_url, output_dir)
            
            return None
        
        print(f"Meeting ID: {meeting_id}")
        
        # Получаем информацию о записи
        recording_info = self.get_recording_info(meeting_id)
        
        if not recording_info:
            print("✗ Не удалось получить информацию о записи")
            return None
        
        # Ищем MP4 файл
        files = recording_info.get('recording_files', [])
        
        for file in files:
            if file.get('file_type') == 'MP4':
                download_url = file.get('download_url')
                if download_url:
                    return self.download_recording(download_url, output_dir)
        
        print("✗ MP4 файл не найден в записи")
        return None


if __name__ == "__main__":
    # Учетные данные из Zoom OAuth App
    ACCOUNT_ID = "fC3gVVJdQKOWDPQbo05aIAQGJQ_02mSbWNDSfMORLTFQyN3E8MCZSgk2phk1yEgfIIiMiKuiSPFM"
    CLIENT_ID = input("Введи Client ID: ").strip() or "YOUR_CLIENT_ID"
    CLIENT_SECRET = input("Введи Client Secret (или Secret Token i5D0kKmMQZOwLxXOvcIB5w): ").strip() or "i5D0kKmMQZOwLxXOvcIB5w"
    
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
            print("\nТеперь можно обработать видео:")
            print(f"python scripts/video_processing/run_zoom_processing.py")
            print("=" * 60)
        else:
            print("\n✗ Не удалось скачать видео")
            
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        print("\nПроверь:")
        print("1. Правильность Client ID и Client Secret")
        print("2. Права доступа OAuth приложения (нужен scope: recording:read)")
        print("3. Доступность записи для твоего аккаунта")
