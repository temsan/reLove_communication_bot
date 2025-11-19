# Docker Setup для reLove Communication Bot

## Структура контейнеров

- **relove_postgres** (существующий) - основная БД с данными профилей
- **relove_communication_bot-redis-1** - Redis для FSM storage и кэша
- **relove_communication_bot-qdrant-1** - Qdrant для поиска похожих пользователей
- **relove_communication_bot-bot-1** - сам бот (при запуске через docker-compose)

## Запуск контейнеров

### 1. Запустить Redis и Qdrant
```bash
docker-compose up -d redis qdrant
```

### 2. Запустить бота в контейнере
```bash
docker-compose up -d bot
```

### 3. Просмотр логов
```bash
docker-compose logs -f bot
```

### 4. Остановить все контейнеры
```bash
docker-compose down
```

## Важно!

- **Существующая БД (relove_postgres) НЕ затирается** - она запущена отдельно и используется как есть
- Бот подключается к БД через `host.docker.internal:5432` (для Windows/Mac) или `localhost:5432` (для Linux)
- Redis и Qdrant запускаются в отдельной сети `relove_network`

## Переменные окружения

Используется `.env` файл для локального запуска и `.env.docker` для контейнера.

Основные переменные:
- `BOT_TOKEN` - токен Telegram бота
- `DB_URL` - строка подключения к PostgreSQL
- `LLM_API_KEY` - ключ OpenRouter API
- `TG_API_ID`, `TG_API_HASH` - для Telethon

## Локальный запуск (без Docker)

```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
python -m relove_bot
```

## Проверка здоровья контейнеров

```bash
docker-compose ps
```

Все контейнеры должны быть в статусе `Up` с `health: healthy` (после инициализации).
