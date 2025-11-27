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

def download_zoom_video_selenium(zoom_url, passcode=None, output_dir="data/videos", zoom_email=None, zoom_password=None):
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
            cookie_selectors = [
                "//button[contains(text(), 'ПРИНИМАТЬ')]",
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'Принять')]",
                "//button[contains(@class, 'accept')]",
                "//button[@id='onetrust-accept-btn-handler']",
                "//*[@id='onetrust-accept-btn-handler']"
            ]
            
            for selector in cookie_selectors:
                try:
                    cookie_btn = driver.find_element(By.XPATH, selector)
                    cookie_btn.click()
                    print("✓ Cookie-попап закрыт")
                    time.sleep(1)
                    break
                except:
                    continue
        except:
            pass
        
        # Сохраняем скриншот для отладки
        screenshot_path = output_path / f"zoom_page_{int(time.time())}.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"Скриншот сохранен: {screenshot_path}")
        
        # Проверяем, требуется ли авторизация (ищем форму входа или сообщение)
        needs_auth = False
        try:
            # Проверяем наличие формы входа или сообщения о необходимости авторизации
            auth_indicators = [
                "//input[@type='email']",
                "//input[@placeholder='Электронная почта']",
                "//*[contains(text(), 'Sign in')]",
                "//*[contains(text(), 'Войти')]",
                "//*[contains(text(), 'войдите')]"
            ]
            
            for indicator in auth_indicators:
                try:
                    driver.find_element(By.XPATH, indicator)
                    needs_auth = True
                    break
                except:
                    continue
        except:
            pass
        
        # Если требуется авторизация и есть учетные данные
        if needs_auth and zoom_email and zoom_password:
            try:
                print("Требуется авторизация в Zoom...")
                
                # Пробуем авторизацию через Google (проще и быстрее)
                try:
                    google_btn = driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Google') or contains(., 'Google')]")
                    print("Используем авторизацию через Google...")
                    google_btn.click()
                    time.sleep(3)
                    
                    # Переключаемся на окно Google
                    if len(driver.window_handles) > 1:
                        driver.switch_to.window(driver.window_handles[-1])
                    
                    # Вводим email в Google
                    google_email = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))
                    )
                    google_email.send_keys(zoom_email)
                    
                    # Нажимаем Далее
                    next_btn = driver.find_element(By.XPATH, "//button[contains(., 'Далее') or contains(., 'Next')]")
                    next_btn.click()
                    time.sleep(3)
                    
                    # Вводим пароль Google
                    google_password = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                    )
                    google_password.send_keys(zoom_password)
                    
                    # Нажимаем Далее
                    next_btn = driver.find_element(By.XPATH, "//button[contains(., 'Далее') or contains(., 'Next')]")
                    next_btn.click()
                    
                    print("✓ Авторизация через Google")
                    time.sleep(5)
                    
                    # Возвращаемся к основному окну
                    driver.switch_to.window(driver.window_handles[0])
                    
                except Exception as google_error:
                    print(f"Google OAuth не сработал: {google_error}")
                    print("Пробуем стандартную авторизацию...")
                    
                    # Стандартная авторизация Zoom
                    email_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='email' or @id='email']"))
                    )
                    email_input.clear()
                    email_input.send_keys(zoom_email)
                    
                    print("Email введен, ищем кнопку Далее...")
                    
                    # Ищем кнопку "Далее" разными способами
                    next_btn_found = False
                    next_selectors = [
                        "//button[contains(text(), 'Далее')]",
                        "//button[contains(text(), 'Next')]",
                        "//button[@type='submit']",
                        "//button[contains(@class, 'submit')]",
                        "//input[@type='submit']",
                        "//button[contains(., 'Далее')]",
                        "//span[contains(text(), 'Далее')]/parent::button"
                    ]
                    
                    for selector in next_selectors:
                        try:
                            next_btn = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            print(f"✓ Найдена кнопка: {selector}")
                            next_btn.click()
                            next_btn_found = True
                            time.sleep(3)
                            break
                        except:
                            continue
                    
                    if not next_btn_found:
                        print("⚠️ Кнопка Далее не найдена, пробуем Enter...")
                        from selenium.webdriver.common.keys import Keys
                        email_input.send_keys(Keys.RETURN)
                        time.sleep(3)
                    
                    # Скриншот после нажатия Далее
                    screenshot_path2 = output_path / f"zoom_after_email_{int(time.time())}.png"
                    driver.save_screenshot(str(screenshot_path2))
                    print(f"Скриншот после email: {screenshot_path2}")
                    
                    # Ждем появления поля пароля
                    print("Ожидание поля пароля...")
                    time.sleep(2)
                    
                    # Вводим пароль
                    password_input = WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='password' or @id='password']"))
                    )
                    print("✓ Поле пароля найдено")
                    password_input.clear()
                    password_input.send_keys(zoom_password)
                    
                    print("Пароль введен, ищем кнопку Войти...")
                    
                    # Ищем кнопку "Войти" разными способами
                    login_btn_found = False
                    login_selectors = [
                        "//button[contains(text(), 'Войти')]",
                        "//button[contains(text(), 'Sign In')]",
                        "//button[@type='submit']",
                        "//button[contains(@class, 'submit')]",
                        "//input[@type='submit']",
                        "//button[contains(., 'Войти')]",
                        "//span[contains(text(), 'Войти')]/parent::button",
                        "//button[contains(@id, 'submit')]"
                    ]
                    
                    for selector in login_selectors:
                        try:
                            login_btn = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            print(f"✓ Найдена кнопка Войти: {selector}")
                            login_btn.click()
                            login_btn_found = True
                            break
                        except:
                            continue
                    
                    if not login_btn_found:
                        print("⚠️ Кнопка Войти не найдена, пробуем Enter...")
                        from selenium.webdriver.common.keys import Keys
                        password_input.send_keys(Keys.RETURN)
                
                print("✓ Авторизация выполнена, ожидание...")
                time.sleep(5)
                
                # Возвращаемся к видео если перенаправило
                if zoom_url not in driver.current_url:
                    driver.get(zoom_url)
                    time.sleep(3)
                    
            except Exception as e:
                print(f"Ошибка авторизации: {e}")
                print("Продолжаем без авторизации...")
        
        # Если нужен пароль для записи
        if passcode:
            try:
                print(f"Ввод пароля записи: {passcode}")
                password_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "password"))
                )
                password_input.send_keys(passcode)
                
                submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                submit_btn.click()
                time.sleep(3)
            except:
                print("Поле пароля записи не найдено")
        
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
    # Учетные данные Zoom из .env
    from dotenv import load_dotenv
    load_dotenv()
    
    ZOOM_EMAIL = os.getenv("ZOOM_EMAIL")
    ZOOM_PASSWORD = os.getenv("ZOOM_PASSWORD")
    
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
        
        video_file = download_zoom_video_selenium(
            video['url'], 
            video.get('passcode'),
            zoom_email=ZOOM_EMAIL,
            zoom_password=ZOOM_PASSWORD
        )
        
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
