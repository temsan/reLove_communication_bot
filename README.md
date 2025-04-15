# reLove Communication Bot

## Описание

Минималистичный Telegram-бот для инкрементального хранения и саммаризации пользовательских сообщений с Retrieval-Augmented Generation (RAG) на основе обычной реляционной БД (PostgreSQL) и OpenAI API.

- Все сообщения пользователя агрегируются и саммаризируются через OpenAI.
- Summary и логи хранятся только по user_id в PostgreSQL.
- При запросе /ask бот формирует ответ с учётом истории пользователя (RAG) — без embedding, без векторных БД.

## Архитектура

- **aiogram** — Telegram-бот
- **SQLAlchemy (async)** — работа с PostgreSQL
- **OpenAI API** — генерация summary и RAG-ответов
- **Вся логика поиска — только по user_id**

## Быстрый старт

1. Установите зависимости:
   ```sh
   pip install -r requirements.txt
   ```

2. Заполните переменные окружения (или config.py):
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `DATABASE_URL` (например, postgresql+asyncpg://user:pass@host/db)

3. Проведите миграцию БД (создайте таблицы):
   ```sh
   # Пример с alembic или вручную через SQLAlchemy
   ```

4. Запустите бота:
   ```sh
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
