# 🧭 Быстрая навигация по проекту

## 🚀 Быстрый старт

### Первый запуск
1. [README.md](../README.md) — начните здесь
2. [deployment/DOCKER_SETUP.md](deployment/DOCKER_SETUP.md) — настройка Docker
3. [channel-import/QUICK_START_CHANNEL_IMPORT.md](channel-import/QUICK_START_CHANNEL_IMPORT.md) — импорт пользователей

### Разработка
1. [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) — архитектура
2. [PROJECT_STATUS.md](PROJECT_STATUS.md) — текущий статус
3. [architecture/CODE_EXAMPLES.md](architecture/CODE_EXAMPLES.md) — примеры кода

## 📚 Документация по темам

### Импорт пользователей из каналов
- 🟢 [Быстрый старт](channel-import/QUICK_START_CHANNEL_IMPORT.md)
- 🟡 [Полное руководство](channel-import/CHANNEL_IMPORT_GUIDE.md)
- 🔴 [Техническая документация](channel-import/CHANNEL_IMPORT_SUMMARY.md)
- 📋 [Шпаргалка команд](channel-import/CHANNEL_IMPORT_CHEATSHEET.md)

### Функции бота
- 🤖 [НейроНаташа](features/NATASHA_BOT_README.md) — провокативный бот
- 📨 [Проактивные сообщения](features/PROACTIVE_BOT_IMPLEMENTATION.md)
- 👤 [Обновление профилей](features/PROFILE_UPDATE_STRATEGY.md)

### Развертывание
- 🐳 [Docker Setup](deployment/DOCKER_SETUP.md)
- 🚀 [Deployment Summary](deployment/DEPLOYMENT_SUMMARY.md)

### Архитектура
- 🏗️ [Общая архитектура](architecture/ARCHITECTURE.md)
- 📊 [Диаграммы](architecture/ARCHITECTURE_DIAGRAM.md)
- 💻 [Примеры кода](architecture/CODE_EXAMPLES.md)
- 📋 [Технические требования](architecture/TECHNICAL_REQUIREMENTS_RELOVE_BOT.md)

### Анализ проекта
- 📊 [Индекс анализа](analysis/ANALYSIS_INDEX.md)
- 🔍 [ТЗ vs Реализация](analysis/ANALYSIS_TZ_VS_IMPLEMENTATION.md)
- 🤖 [Анализ Rasa](analysis/RASA_BOT_ANALYSIS.md)

## 🛠️ Скрипты

### База данных
```bash
# Инициализация
python scripts/database/init_db.py

# Бэкап
python scripts/database/backup_database.py
```

### Telegram
```bash
# Авторизация
python scripts/telegram/auth_telegram.py

# Список каналов
python scripts/telegram/quick_channel_list.py
```

### Профили
```bash
# Заполнение профилей
python scripts/profiles/fill_profiles.py --all

# Импорт из каналов
python scripts/profiles/fill_profiles_from_channels.py --all
```

### Запуск
```bash
# Запуск бота
python scripts/utils/run_bot.py

# Запуск тестов
python scripts/testing/run_tests.py
```

## 📁 Структура проекта

```
reLove_communication_bot/
├── 📁 relove_bot/           # Код бота
├── 📁 scripts/              # Скрипты
│   ├── database/            # БД
│   ├── telegram/            # Telegram
│   ├── profiles/            # Профили
│   ├── analysis/            # Анализ
│   ├── testing/             # Тесты
│   ├── youtube/             # YouTube
│   └── utils/               # Утилиты
├── 📁 docs/                 # Документация
│   ├── analysis/            # Анализ
│   ├── architecture/        # Архитектура
│   ├── channel-import/      # Импорт
│   ├── deployment/          # Деплой
│   └── features/            # Функции
├── 📁 backups/              # Бэкапы
├── 📁 tests/                # Тесты
└── 📁 alembic/              # Миграции
```

## 🔗 Полезные ссылки

- [README.md](README.md) — индекс документации
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — статус проекта
- [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) — дорожная карта
- [RECOMMENDATIONS.md](RECOMMENDATIONS.md) — рекомендации
- [../scripts/README.md](../scripts/README.md) — описание скриптов
- [../backups/README.md](../backups/README.md) — работа с бэкапами

## 💡 Частые вопросы

### Как начать работу?
1. Прочитайте [README.md](../README.md)
2. Настройте `.env` файл
3. Запустите `docker-compose up -d`
4. Примените миграции: `alembic upgrade head`

### Как импортировать пользователей?
См. [channel-import/QUICK_START_CHANNEL_IMPORT.md](channel-import/QUICK_START_CHANNEL_IMPORT.md)

### Как добавить новую функцию?
1. Изучите [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md)
2. Посмотрите [architecture/CODE_EXAMPLES.md](architecture/CODE_EXAMPLES.md)
3. Проверьте [PROJECT_STATUS.md](PROJECT_STATUS.md) для приоритетов

### Где найти скрипты?
См. [../scripts/README.md](../scripts/README.md) — полный список с описанием

### Как сделать бэкап?
См. [../backups/README.md](../backups/README.md) — инструкции по бэкапам
