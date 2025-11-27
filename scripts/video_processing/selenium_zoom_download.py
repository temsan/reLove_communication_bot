"""
Автоматическое скачивание Zoom видео через Selenium
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
from pathlib import Path

def download_zoom_with_selenium(zoom_url, passcode=None, download_dir=None):
    """
    Скачивает Zoom видео через Selenium
    """
    if download_dir is None:
        download_dir = str(Path("data/videos").absolute())
    
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    
    chrome_options = Options()
    
    # Настройки для автоматического скачивания
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Раскомментируй для фонового режима (без окна браузера)
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print(f"Открываем: {zoom_url}")
        driver.get(zoom_url)
        
        # Ждем загрузки страницы
        time.sleep(3)
        
        # Если нужен пароль
        if passcode:
            try:
                print(f"Ввод пароля: {passcode}")
                password_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "password"))
                )
                password_input.send_keys(passcode)
                
                # Нажимаем кнопку Submit
                submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                submit_btn.click()
                
                time.sleep(3)
            except:
                print("Поле пароля не найдено или не требуется")
        
        # Ищем кнопку Download
        print("Поиск кнопки Download...")
        
        download_selectors = [
            "//button[contains(text(), 'Download')]",
            "//a[contains(text(), 'Download')]",
            "//button[contains(@class, 'download')]",
            "//a[contains(@class, 'download')]",
            "//button[contains(text(), 'Скачать')]",
            "//a[contains(text(), 'Скачать')]"
        ]
        
        download_btn = None
        for selector in download_selectors:
            try:
                download_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                break
            except:
                continue
        
        if download_btn:
            print("✓ Кнопка Download найдена, начинаем скачивание...")
            download_btn.click()
            
            print("\nСкачивание началось...")
            print(f"Файлы сохраняются в: {download_dir}")
            print("\nОжидание завершения скачивания (это может занять время)...")
            
            # Ждем появления файла
            initial_files = set(os.listdir(download_dir))
            
            # Ждем до 5 минут
            max_wait = 300
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                time.sleep(2)
                current_files = set(os.listdir(download_dir))
                new_files = current_files - initial_files
                
                # Проверяем завершенные файлы (не .crdownload, не .tmp)
                completed = [f for f in new_files if not f.endswith(('.crdownload', '.tmp', '.part'))]
                
                if completed:
                    video_file = Path(download_dir) / completed[0]
                    print(f"\n✓ Видео скачано: {video_file}")
                    return video_file
                
                # Показываем прогресс
                in_progress = [f for f in new_files if f.endswith(('.crdownload', '.tmp', '.part'))]
                if in_progress:
                    for f in in_progress:
                        size = os.path.getsize(Path(download_dir) / f) / 1024 / 1024
                        print(f"\rСкачивание... {size:.1f} MB", end='')
            
            print("\n✗ Превышено время ожидания")
            return None
        else:
            print("✗ Кнопка Download не найдена")
            print("\nВозможные причины:")
            print("1. Требуется авторизация в Zoom")
            print("2. Запись недоступна для скачивания")
            print("3. Страница загрузилась не полностью")
            
            # Сохраняем скриншот для отладки
            screenshot_path = Path(download_dir) / "zoom_page_debug.png"
            driver.save_screenshot(str(screenshot_path))
            print(f"\nСкриншот сохранен: {screenshot_path}")
            
            return None
            
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        return None
    finally:
        print("\nЗакрытие браузера...")
        driver.quit()


if __name__ == "__main__":
    # Ссылки для скачивания
    videos = [
        {
            "url": "https://us06web.zoom.us/rec/share/8XJFkKaQ5_lH32KOhX-xzN7TOe9wTb3IHo9k3dLXSuSFA7G9sWZnsmNr-60ne8Vd.Jc0yHUzjmtgZs9Zl",
            "passcode": "^Ufw4B8k"
        },
        {
            "url": "https://us06web.zoom.us/rec/share/4Fsn5HhQ9hCV1_fcYxXmt2K1pdN1rAM1vTg_l_Zrencd603ns4crRKO8AeKMPpdK.I6qLpkl1nvXF8UnI",
            "passcode": None  # Если есть пароль - добавь сюда
        }
    ]
    
    print("=" * 60)
    print("Автоматическое скачивание Zoom видео через Selenium")
    print("=" * 60)
    print("\nУстанови Selenium и ChromeDriver:")
    print("pip install selenium")
    print("=" * 60)
    
    downloaded_files = []
    
    for i, video in enumerate(videos, 1):
        print(f"\n\n{'='*60}")
        print(f"Видео {i}/{len(videos)}")
        print('='*60)
        
        video_file = download_zoom_with_selenium(
            video['url'],
            video.get('passcode')
        )
        
        if video_file:
            downloaded_files.append(video_file)
    
    # Обработка скачанных видео
    if downloaded_files:
        print("\n\n" + "=" * 60)
        print(f"✓ Скачано видео: {len(downloaded_files)}")
        print("=" * 60)
        
        process = input("\nОбработать видео (кроп + очистка + ватермарк)? (y/n): ").strip().lower()
        
        if process == 'y':
            from process_zoom_video import VideoProcessor
            
            processor = VideoProcessor()
            
            for video_file in downloaded_files:
                print(f"\n\nОбработка: {video_file.name}")
                print("-" * 60)
                
                try:
                    # 1. Кроп
                    print("1. Кроп в вертикальный формат...")
                    cropped = processor.crop_to_vertical(video_file)
                    
                    # 2. Очистка звука
                    print("2. Очистка звука...")
                    clean = processor.clean_audio(cropped)
                    
                    # 3. Ватермарк
                    print("3. Наложение ватермарка...")
                    final = processor.add_watermark(clean, "Private")
                    
                    print(f"\n✓ Готово: {final}")
                    
                except Exception as e:
                    print(f"✗ Ошибка обработки: {e}")
    else:
        print("\n✗ Видео не скачаны")
