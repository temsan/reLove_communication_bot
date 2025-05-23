import os
import asyncio
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import UsernameNotOccupiedError, UsernameInvalidError
import requests

API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
SESSION = os.getenv('TG_SESSION', 'relove_bot')

# Получение списка пользователей YouTube через YouTube Data API v3
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
CHANNEL_ID = os.getenv('YOUTUBE_CHANNEL_ID')

# Получаем никнеймы комментаторов к последним 50 видео
YOUTUBE_API_URL = 'https://www.googleapis.com/youtube/v3/'


def get_youtube_usernames(api_key, channel_id, max_results=50):
    usernames = set()
    # Получаем последние видео
    videos_url = f"{YOUTUBE_API_URL}search?key={api_key}&channelId={channel_id}&part=snippet,id&order=date&maxResults={max_results}"
    resp = requests.get(videos_url)
    data = resp.json()
    video_ids = [item['id']['videoId'] for item in data.get('items', []) if item['id'].get('videoId')]
    for vid in video_ids:
        comments_url = f"{YOUTUBE_API_URL}commentThreads?key={api_key}&videoId={vid}&part=snippet&maxResults=100"
        resp = requests.get(comments_url)
        if resp.status_code != 200:
            continue
        cdata = resp.json()
        for item in cdata.get('items', []):
            author = item['snippet']['topLevelComment']['snippet'].get('authorDisplayName', '')
            # Только если это похоже на Telegram-username
            if author and (author.startswith('@') or author.replace('_', '').isalnum()):
                usernames.add(author.lstrip('@'))
    return list(usernames)

async def search_telegram_by_username(usernames):
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    results = []
    for username in usernames:
        username = username.strip().lstrip('@')
        if not username:
            continue
        try:
            entity = await client.get_entity(int(username))
            results.append(f"{username}: найден — id={entity.id}, имя={getattr(entity, 'first_name', '')}, ссылка=https://t.me/{username}")
        except (UsernameNotOccupiedError, UsernameInvalidError):
            results.append(f"{username}: не найден")
        except Exception as e:
            results.append(f"{username}: ошибка {e}")
    await client.disconnect()
    return results

if __name__ == '__main__':
    if not YOUTUBE_API_KEY or not CHANNEL_ID:
        print('YOUTUBE_API_KEY и YOUTUBE_CHANNEL_ID должны быть заданы в переменных окружения!')
        exit(1)
    usernames = get_youtube_usernames(YOUTUBE_API_KEY, CHANNEL_ID)
    print(f"Из YouTube получено username: {len(usernames)}")
    found = asyncio.run(search_telegram_by_username(usernames))
    with open('found_telegram_users.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(found))
    print("Результаты поиска сохранены в found_telegram_users.txt")
