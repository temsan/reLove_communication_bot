"""
Отладка: сохраняем HTML страницы Zoom для анализа
"""
import requests
from pathlib import Path

url = "https://us06web.zoom.us/rec/play/Lch7ENL7eu3iPNYzvXGCJ-BKVf1TvkdAS-m8UFbzn62OEwwN7iSMKqwSRV2eR1CjXaLI5WIvyciNyi1L.zDWx3LVOt90iNF2O?eagerLoadZvaPages=sidemenu.billing.plan_management&accessLevel=meeting&canPlayFromShare=true&from=share_recording_detail&continueMode=true&componentName=rec-play&originRequestUrl=https%3A%2F%2Fus06web.zoom.us%2Frec%2Fshare%2Fl2gqtAe5vJNDIKeITgSHdYRY0S7VCYdl1niakvgZ4jtn6udMIPHOQGAVCalX8GK4.oy18D3f8RMaCuNB3"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")

output_path = Path("data/videos/zoom_page.html")
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    f.write(response.text)

print(f"HTML сохранен: {output_path}")
print(f"Размер: {len(response.text)} байт")

# Ищем ключевые слова
keywords = ['mp4', 'video', 'download', 'viewMp4Url', 'playUrl', 'recordingUrl']
for keyword in keywords:
    count = response.text.lower().count(keyword.lower())
    if count > 0:
        print(f"Найдено '{keyword}': {count} раз")
