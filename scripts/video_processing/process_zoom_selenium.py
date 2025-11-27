"""
Скачивание Zoom видео через Selenium (требует авторизации в браузере)
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import requests
from pathlib import Path

def download_zoom_video_selenium(zoom_url, passcode=None, output_dir="data/videos"):
    """
    Скачивает Zoom видео через Selenium с автоматическим нажатием Download
    """
    output_path = Path(output_dir).absolute()
    output_path.mkdir(parents=True, exist_ok=True)
    
    chrome_options = Options()
    
    # Настройки для автоматического скачивания
    prefs = {
        "download.default_directory": str(output_path),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print(f"Открываем: {zoom_url}")
        driver.get(zoom_url)
        time.sleep(3)
        
        # Закрываем cookie диалог если есть
        try:
            cookie_accept = driver.find_element(By.XPATH, "//button[contains(text(), 'ПРИНИМАТЬ') or contains(text(), 'Accept')]")
            cookie_accept.click()
            time.sleep(1)
        except:
            pass
        
        # Если нужен пароль
        if passcode:
            try:
                print(f"Ввод пароля: {passcode}")
                password_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "password"))
                )
                password_input.send_keys(passcode)
                
                submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                submit_btn.click()
                time.sleep(3)
            except:
                print("Поле пароля не найдено")
        
        # Ищем кнопку Download
        print("Поиск кнопки Download...")
        
        download_selectors = [
            "//button[contains(text(), 'Download')]",
            "//a[contains(text(), 'Download')]",
            "//button[contains(@class, 'download')]",
            "//a[contains(@class, 'download')]",
            "//button[contains(text(), 'Скачать')]"
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
            
            print(f"\nСкачивание в: {output_path}")
            print("Ожидание завершения...")
            
            # Ждем появления файла
            initial_files = set(os.listdir(output_path))
            
            max_wait = 300  # 5 минут
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                time.sleep(2)
                current_files = set(os.listdir(output_path))
                new_files = current_files - initial_files
                
                completed = [f for f in new_files if not f.endswith(('.crdownload', '.tmp', '.part'))]
                
                if completed:
                    video_file = output_path / completed[0]
                    print(f"\n✓ Видео скачано: {video_file}")
                    return video_file
                
                in_progress = [f for f in new_files if f.endswith(('.crdownload', '.tmp', '.part'))]
                if in_progress:
                    for f in in_progress:
                        size = os.path.getsize(output_path / f) / 1024 / 1024
                        print(f"\rСкачивание... {size:.1f} MB", end='')
            
            print("\n✗ Превышено время ожидания")
            return None
        else:
            print("✗ Кнопка Download не найдена")
            screenshot_path = output_path / "zoom_debug.png"
            driver.save_screenshot(str(screenshot_path))
            print(f"Скриншот: {screenshot_path}")
            return None
            
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        return None
    finally:
        driver.quit()


if __name__ == "__main__":
    videos = [
        {
            "url": "https://us06web.zoom.us/rec/share/8XJFkKaQ5_lH32KOhX-xzN7TOe9wTb3IHo9k3dLXSuSFA7G9sWZnsmNr-60ne8Vd.Jc0yHUzjmtgZs9Zl",
            "passcode": "^Ufw4B8k"
        },
        {
            "url": "https://us06web.zoom.us/rec/share/4Fsn5HhQ9hCV1_fcYxXmt2K1pdN1rAM1vTg_l_Zrencd603ns4crRKO8AeKMPpdK.I6qLpkl1nvXF8UnI",
            "passcode": None
        }
    ]
    
    print("=" * 60)
    print("Автоматическое скачивание Zoom через Selenium")
    print("=" * 60)
    
    downloaded = []
    
    for i, video in enumerate(videos, 1):
        print(f"\n{'='*60}")
        print(f"Видео {i}/{len(videos)}")
        print('='*60)
        
        video_file = download_zoom_video_selenium(video['url'], video.get('passcode'))
        
        if video_file:
            downloaded.append(video_file)
    
    # Обработка
    if downloaded:
        print(f"\n\n{'='*60}")
        print(f"✓ Скачано: {len(downloaded)}")
        print('='*60)
        
        process = input("\nОбработать (кроп + очистка + ватермарк)? (y/n): ").strip().lower()
        
        if process == 'y':
            from process_zoom_video import VideoProcessor
            
            processor = VideoProcessor()
            
            for video_file in downloaded:
                print(f"\n\nОбработка: {video_file.name}")
                print("-" * 60)
                
                try:
                    cropped = processor.crop_to_vertical(video_file)
                    clean = processor.clean_audio(cropped)
                    final = processor.add_watermark(clean, "Private")
                    print(f"\n✓ Готово: {final}")
                except Exception as e:
                    print(f"✗ Ошибка: {e}")
