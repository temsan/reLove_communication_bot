# 🛠️ Scripts

Коллекция утилит и скриптов для управления проектом.

## Структура

### 💾 Database (`database/`)
Скрипты для работы с базой данных:
- `init_db.py` — инициализация базы данных
- `backup_database.py` — создание бэкапа БД
- `backup_db_docker.ps1` — бэкап через Docker (PowerShell)
- `check_tables.py` — проверка таблиц
- `add_missing_columns.py` — добавление недостающих колонок
- `create_proactive_tables.py` / `.sql` — создание таблиц для проактивных сообщений
- `init_youtube_chat_table.py` — инициализация таблицы YouTube чатов

### 📱 Telegram (`telegram/`)
Скрипты для работы с Telegram API:
- `auth_telegram.py` — авторизация в Telegram
- `test_telethon_connection.py` — тест подключения Telethon
- `quick_channel_list.py` — быстрый список каналов
- `import_users_from_chats.py` — импорт пользователей из чатов
- `count_subscriptions.py` — подсчет подписок

### 👤 Profiles (`profiles/`)
Скрипты для работы с профилями пользователей:
- `fill_profiles.py` — основной скрипт заполнения профилей
- `fill_profiles_from_channels.py` — заполнение из каналов
- `fill_profiles_llm.py` — заполнение через LLM
- `fill_profiles_v2.py` — версия 2
- `simple_fill_profiles.py` — упрощенная версия
- `force_fill_and_mark_sleeping.py` — принудительное заполнение
- `detect_gender_all.py` — определение пола всех пользователей
- `fix_unknown_gender.py` — исправление неизвестного пола
- `update_gender_from_markers.py` — обновление пола из маркеров
- `gender_stats.py` — статистика по полу
- `README_FILL_PROFILES_FROM_CHANNELS.md` — документация

### 📊 Analysis (`analysis/`)
Скрипты для анализа данных:
- `analyze_chat_llm.py` — анализ чата через LLM
- `analyze_natasha_sandra_game.py` — анализ игры Наташа-Сандра
- `analyze_relove_channel.py` — анализ канала reLove
- `summarize_relove_channel.py` — саммаризация канала
- `get_timur_sosa_messages.py` — получение сообщений Тимура Соса
- `test_timur_sosa.py` — тест для Тимура Соса
- `parse_ritual_meditations.py` — парсинг ритуальных медитаций
- `find_yt_users_in_telegram.py` — поиск YouTube пользователей в Telegram

### 🧪 Testing (`testing/`)
Тестовые скрипты:
- `run_tests.py` — запуск тестов
- `test_import_safe.py` — тест безопасного импорта
- `test_llm_connection.py` — тест подключения к LLM
- `test_sheet_format.py` — тест формата таблиц
- `test_ssl.py` — тест SSL
- `TEST_SHEETS_CREATION.md` — документация по тестам

### 📺 YouTube (`youtube/`)
Скрипты для работы с YouTube:
- `youtube_chat_parser.py` — парсер YouTube чатов
- `README_YOUTUBE_CHAT_PARSER.md` — документация
- `requirements-youtube.txt` — зависимости

### 🔧 Utils (`utils/`)
Утилиты общего назначения:
- `run_bot.py` — запуск бота
- `run_ngrok.py` — запуск ngrok
- `build_docs.py` — сборка документации
- `dashboard.py` — дашборд
- `install_spacy_model.py` — установка модели spaCy

## Быстрый старт

### Инициализация БД
```bash
python scripts/database/init_db.py
```

### Авторизация в Telegram
```bash
python scripts/telegram/auth_telegram.py
```

### Заполнение профилей
```bash
python scripts/profiles/fill_profiles.py --all --batch-size 20
```

### Запуск бота
```bash
python scripts/utils/run_bot.py
```

### Создание бэкапа
```bash
python scripts/database/backup_database.py
# или через Docker
.\scripts\database\backup_db_docker.ps1
```

## Примечания

- Большинство скриптов требуют настроенный `.env` файл
- Для работы с Telegram API нужны `TG_API_ID` и `TG_API_HASH`
- Для LLM скриптов нужен `LLM_API_KEY`
