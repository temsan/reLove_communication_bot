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

- **aiogram** — Telegram-бот
- **SQLAlchemy (async)** — работа с PostgreSQL
- **OpenAI API** — генерация summary и RAG-ответов
- **Вся логика поиска — только по user_id**
- **Qdrant** — векторное хранилище для хранения эмбеддингов

## Быстрый старт

1. Установите зависимости (через Poetry или pip):
   ```bash
   # С помощью Poetry
   poetry install

   # Или без Poetry (через pip)
   python -m pip install --upgrade pip
   python -m pip install -e .
   ```

2. Заполните переменные окружения (или config.py):
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `DATABASE_URL` (например, postgresql+asyncpg://user:pass@host/db)

3. Проведите миграцию БД (создайте таблицы):
   ```sh
   # Пример с alembic или вручную через SQLAlchemy
   ```

4. Запустите Qdrant (векторная база) локально:
   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```

5. Запустите бота:
   ```bash
   python -m relove_bot.main
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

## Масштабирование и поддержка

- Stateless: можно запускать несколько копий бота
- PostgreSQL можно шардировать и реплицировать
- Нет embedding, нет векторных БД — только SQL и OpenAI

---

**Если нужна интеграция с облаком, docker-compose, автотесты — пишите!**
