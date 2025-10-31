# ReLove Communication Bot

Телеграм-бот для психологической диагностики и интеграции с платформой relove.ru.

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/your-username/relove_communication_bot.git
cd relove_communication_bot
```

2. Создайте виртуальное окружение и установите зависимости:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
pip install -r requirements.txt
```

3. Создайте файл `.env` в корневой директории проекта со следующими настройками:
```env
# Bot settings
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321  # Comma-separated list of admin user IDs

# Database settings
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASS=your_db_password_here
DB_NAME=relove_bot
DB_ECHO=false

# Redis settings (optional)
USE_REDIS=false
REDIS_URL=redis://localhost:6379/0

# Logging settings
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
LOG_DIR=logs
LOG_FILE=bot.log

# Webhook settings (optional)
WEBHOOK_HOST=https://your-domain.com
WEBHOOK_SECRET=your_webhook_secret_here
```

4. Создайте базу данных PostgreSQL:
```bash
createdb relove_bot
```

5. Примените миграции:
```bash
alembic upgrade head
```

## Запуск

1. Запустите бота:
```bash
python -m relove_bot.bot
```

## Структура проекта

```
relove_bot/
├── alembic/              # Миграции базы данных
├── core/                 # Основные компоненты
├── db/                   # Модели и сессии базы данных
├── handlers/             # Обработчики команд
├── keyboards/            # Клавиатуры
├── middlewares/          # Middleware компоненты
├── states/               # Состояния FSM
├── bot.py               # Основной файл бота
├── config.py            # Конфигурация
└── web.py               # Веб-интерфейс (опционально)
```

## Разработка

1. Создание новой миграции:
```bash
alembic revision --autogenerate -m "description"
```

2. Применение миграций:
```bash
alembic upgrade head
```

3. Откат миграции:
```bash
alembic downgrade -1
```

## Логирование

Логи сохраняются в директории `logs/` в формате:
- `bot.log` - основной лог бота
- `web.log` - лог веб-интерфейса (если используется)

## Лицензия

MIT

## Стандарт работы с Telegram сущностями (tg_user, channel, peer и др.)

- Если объект (tg_user, channel, peer, chat и др.) уже получен через client.get_entity или другой Telethon-метод, всегда передавайте его по цепочке во все функции и сервисы, где он нужен.
- Не делайте повторных запросов к Telegram API для одной и той же сущности в рамках одной операции.
- Все функции и сервисы, которым нужна сущность, должны принимать её как аргумент и использовать, если она уже есть.
- Это повышает эффективность, уменьшает задержки и снижает риск rate limit.

**Пример:**
```python
# Получаем channel один раз
channel = await client.get_entity(channel_id)
# Передаём channel по цепочке
await do_something_with_channel(channel)
```

# Стандарт работы с Telegram User (tg_user)

- Если объект tg_user уже получен (через client.get_entity), всегда передавайте его во все функции и сервисы, где он нужен (например, для определения пола, генерации summary и т.д.).
- Не делайте повторных запросов к Telegram API для одного и того же пользователя в рамках одной операции.
- Все функции и сервисы, которым нужен tg_user, должны принимать его как аргумент и использовать, если он уже есть.
- Это повышает эффективность, уменьшает задержки и снижает риск rate limit.


## Описание

Telegram-бот для инкрементального хранения и саммаризации пользовательских сообщений с Retrieval-Augmented Generation (RAG) на основе обычной реляционной БД (PostgreSQL) и OpenAI API.

- Все сообщения пользователя агрегируются и саммаризируются через OpenAI.
- Summary и логи хранятся только по user_id в PostgreSQL.
- При запросе /ask бот формирует ответ с учётом истории пользователя (RAG) — без embedding, без векторных БД.

## Архитектура

- **aiogram 3.3.0** — Telegram-бот фреймворк
- **SQLAlchemy (async)** — работа с PostgreSQL
- **LLM API** (OpenAI/OpenRouter/Groq) — генерация summary и RAG-ответов
- **Telethon** — работа с Telegram API для анализа каналов
- **Rasa** — дополнительный NLP-бот (опционально)
- **Вся логика поиска — только по user_id в PostgreSQL**

**Примечание:** Qdrant используется опционально для команды `/similar` (поиск похожих пользователей). Основная работа идёт через PostgreSQL и LLM.

## Быстрый старт

1. **Клонируйте репозиторий:**
   ```bash
   git clone <repository_url>
   cd reLove_communication_bot
   ```

2. **Создайте виртуальное окружение и установите зависимости:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   pip install -r requirements.txt
   ```

3. **Настройте переменные окружения:**
   ```bash
   # Скопируйте шаблон:
   cp .env.example .env
   # Или на Windows:
   copy .env.example .env
   
   # Отредактируйте .env файл, заполнив все необходимые переменные
   ```
   
   Минимально необходимые переменные:
   - `BOT_TOKEN` — токен Telegram бота
   - `DB_URL` — URL базы данных PostgreSQL
   - `LLM_API_KEY` — ключ для LLM API (OpenAI/OpenRouter)
   - `TG_API_ID`, `TG_API_HASH` — для работы с Telegram API
   - `OUR_CHANNEL_ID` — ID канала для анализа

4. **Настройте базу данных:**
   ```bash
   # Запустите PostgreSQL через Docker:
   docker-compose up -d db
   
   # Примените миграции:
   alembic upgrade head
   ```

5. **Запустите бота:**
   ```bash
   python -m relove_bot.bot
   ```
   
   Или используйте скрипт:
   ```bash
   python scripts/run_bot.py
   ```

6. **Опционально — запустите Qdrant для команды /similar:**
   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```

## Основные файлы

- `db/models.py` — модели User и UserActivityLog
- `db/session.py` — асинхронная сессия SQLAlchemy
- `rag/llm.py` — функции для генерации summary и RAG-ответа через OpenAI
- `rag/pipeline.py` — получение контекста пользователя из БД
- `handlers/common.py` — обработка сообщений и команды /ask

## Пример работы

- Любое сообщение пользователя — сохраняется summary в БД
- `/ask <вопрос>` — бот ищет последние summary пользователя и даёт ответ через OpenAI

## Основные команды бота

- `/start` — запустить/перезапустить бота
- `/help` — справка
- `/diagnostic` — гибкая диагностика через диалог (LLM адаптирует вопросы)
- `/start_journey` — традиционная диагностика с выбором из вариантов
- `/natasha` — провокативная сессия с Наташей (путь героя Кэмпбелла)
- `/streams` — информация о потоках reLove
- `/my_session_summary` — сводка текущей провокативной сессии
- `/my_metaphysical_profile` — метафизический профиль пользователя

## Основные компоненты

- `relove_bot/handlers/` — обработчики команд и сообщений
  - `flexible_diagnostic.py` — гибкая LLM-диагностика
  - `provocative_natasha.py` — провокативный бот в стиле Наташи
  - `psychological_journey.py` — традиционная диагностика
- `relove_bot/services/` — бизнес-логика
  - `llm_service.py` — работа с LLM API
  - `profile_service.py` — анализ и обновление профилей
  - `telegram_service.py` — работа с Telegram API
- `relove_bot/utils/fill_profiles.py` — скрипт массового обновления профилей
- `scripts/fill_profiles.py` — CLI для запуска обновления профилей

## Масштабирование и поддержка

- **Stateless:** можно запускать несколько копий бота
- **PostgreSQL:** можно шардировать и реплицировать
- **Основная работа:** SQL + LLM (без обязательных векторных БД)
- **Qdrant:** опционально для поиска похожих пользователей (`/similar`)

## Разработка

См. `docs/` для подробной документации:
- `docs/installation.rst` — установка
- `docs/development.rst` — разработка
- `docs/configuration.rst` — конфигурация
- `ARCHITECTURE.md` — архитектура проекта
