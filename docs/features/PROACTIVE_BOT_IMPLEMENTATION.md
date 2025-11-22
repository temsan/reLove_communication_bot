# Проактивный бот - Реализация

## Что реализовано

### 1. Модели данных (relove_bot/db/models.py)
- ✅ `ProactiveTrigger` - триггеры для проактивных сообщений
- ✅ `UserInteraction` - трекинг взаимодействий
- ✅ `ProactivityConfig` - конфигурация проактивности
- ✅ Enums: `TriggerTypeEnum`, `InteractionTypeEnum`

### 2. UI Manager (relove_bot/services/ui_manager.py)
- ✅ `create_quick_replies()` - адаптивные кнопки под этап пути
- ✅ `format_progress_indicator()` - визуализация прогресса с эмодзи
- ✅ `apply_relove_styling()` - минималистичное форматирование
- ✅ `STAGE_QUICK_REPLIES` - кнопки для каждого этапа

### 3. STAGE_BEHAVIORS (relove_bot/core/journey_behaviors.py)
- ✅ Уровни провокации для каждого этапа (soft/medium/hard)
- ✅ Техники для каждого этапа
- ✅ Дополнения к промптам для адаптации стиля

### 4. Trigger Engine (relove_bot/services/trigger_engine.py)
- ✅ `check_inactivity_triggers()` - проверка неактивных пользователей
- ✅ `check_milestone_triggers()` - проверка завершённых этапов
- ✅ `check_pattern_triggers()` - обнаружение паттернов избегания
- ✅ `schedule_proactive_message()` - планирование сообщений
- ✅ `get_pending_triggers()` - получение готовых триггеров

### 5. Message Orchestrator (relove_bot/services/message_orchestrator.py)
- ✅ `process_user_message()` - обработка входящих сообщений
- ✅ `generate_proactive_message()` - генерация проактивных сообщений
- ✅ `format_message_with_ui()` - форматирование с UI элементами
- ✅ Интеграция с Journey Service и UI Manager

### 6. Rate Limiter (relove_bot/services/proactive_rate_limiter.py)
- ✅ `check_proactive_limit()` - проверка лимита сообщений в день
- ✅ `check_time_window()` - проверка временного окна (8:00-22:00)
- ✅ `can_send_proactive()` - комплексная проверка всех условий

### 7. Natasha Proactive Service (relove_bot/services/natasha_proactive.py)
- ✅ `generate_stage_aware_response()` - ответы с учётом этапа
- ✅ `generate_proactive_reminder()` - напоминания при неактивности
- ✅ `generate_milestone_message()` - поздравления с этапами
- ✅ `detect_avoidance_pattern()` - обнаружение избегания

### 8. Фоновые задачи (relove_bot/tasks/background_tasks.py)
- ✅ `check_proactive_triggers_task()` - проверка триггеров каждые 15 мин
- ✅ `send_proactive_messages_task()` - отправка сообщений каждую минуту

### 9. Обработчики кнопок меню (relove_bot/handlers/common.py)
- ✅ "📊 Моя сессия" - показ текущей сессии и прогресса
- ✅ "🌌 Мой профиль" - показ профиля и метафизики
- ✅ "🔥 Потоки" - показ доступных потоков
- ✅ "⏸ Пауза" - приостановка проактивности
- ✅ "▶️ Продолжить" - возобновление проактивности

## Что нужно сделать

### 1. Миграция БД
```bash
# Создать миграцию
alembic revision --autogenerate -m "Add proactive triggers and interactions"

# Применить миграцию
alembic upgrade head
```

### 2. Запуск фоновых задач
Добавить в `relove_bot/bot.py`:

```python
from relove_bot.tasks.background_tasks import (
    check_proactive_triggers_task,
    send_proactive_messages_task
)

# В функции main() после создания бота:
async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()
    
    # ... регистрация handlers ...
    
    # Запуск фоновых задач
    asyncio.create_task(check_proactive_triggers_task())
    asyncio.create_task(send_proactive_messages_task(bot))
    
    await dp.start_polling(bot)
```

### 3. Интеграция с provocative_natasha.py
Обновить обработчики для использования MessageOrchestrator:

```python
from relove_bot.services.message_orchestrator import MessageOrchestrator

@router.message(ProvocativeStates.waiting_for_response)
async def handle_provocative_response(message: Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    
    # Используем MessageOrchestrator
    orchestrator = MessageOrchestrator(session)
    response = await orchestrator.process_user_message(
        user_id,
        message.text,
        session_type="provocative"
    )
    
    await message.answer(
        response.text,
        reply_markup=response.keyboard,
        parse_mode=response.parse_mode
    )
```

### 4. Настройка Redis (опционально)
Для кэширования сессий создать `relove_bot/core/redis.py`:

```python
import redis.asyncio as redis
from relove_bot.config import settings

redis_client = redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True
)

class SessionCache:
    async def get(self, key: str):
        return await redis_client.get(key)
    
    async def set(self, key: str, value: str, ttl: int = 3600):
        await redis_client.setex(key, ttl, value)
    
    async def delete(self, key: str):
        await redis_client.delete(key)
```

## Тестирование

### 1. Тест UI Manager
```python
from relove_bot.services.ui_manager import UIManager
from relove_bot.db.models import JourneyStageEnum

ui = UIManager()

# Тест quick replies
keyboard = ui.create_quick_replies(JourneyStageEnum.REFUSAL)
print(keyboard)

# Тест progress indicator
progress = ui.format_progress_indicator(
    JourneyStageEnum.MEETING_MENTOR,
    ["Обычный мир", "Зов к приключению"]
)
print(progress)
```

### 2. Тест Trigger Engine
```python
from relove_bot.services.trigger_engine import TriggerEngine
from relove_bot.db.session import async_session

async with async_session() as session:
    engine = TriggerEngine(session)
    
    # Проверка неактивности
    triggers = await engine.check_inactivity_triggers()
    print(f"Created {len(triggers)} inactivity triggers")
    
    # Получение готовых триггеров
    pending = await engine.get_pending_triggers()
    print(f"Pending triggers: {len(pending)}")
```

### 3. Тест Message Orchestrator
```python
from relove_bot.services.message_orchestrator import MessageOrchestrator

async with async_session() as session:
    orchestrator = MessageOrchestrator(session)
    
    response = await orchestrator.process_user_message(
        user_id=123456,
        message="Не знаю что делать",
        session_type="provocative"
    )
    
    print(response.text)
    print(response.keyboard)
```

## Конфигурация

### Параметры проактивности
Настраиваются в таблице `proactivity_config`:

- `max_messages_per_day` - максимум сообщений в день (по умолчанию 2)
- `time_window_start` - начало временного окна (по умолчанию 08:00)
- `time_window_end` - конец временного окна (по умолчанию 22:00)
- `enabled_triggers` - список включённых триггеров

### Типы триггеров
- `inactivity_24h` - неактивность 24 часа
- `milestone_completed` - завершение этапа
- `pattern_detected` - обнаружение паттерна избегания
- `morning_check` - утренняя проверка
- `stage_transition` - переход на новый этап

## Мониторинг

### Логи
Все компоненты логируют свою работу:
- Создание триггеров
- Отправка проактивных сообщений
- Ошибки и retry
- Rate limiting

### Метрики
Можно отслеживать через БД:
- Количество созданных триггеров
- Количество отправленных сообщений
- Процент открытия проактивных сообщений
- Распределение пользователей по этапам пути

## Troubleshooting

### Проактивные сообщения не отправляются
1. Проверить, запущены ли фоновые задачи
2. Проверить логи на ошибки
3. Проверить rate limit в `proactivity_config`
4. Проверить временное окно

### Триггеры не создаются
1. Проверить, есть ли активные сессии
2. Проверить, включены ли типы триггеров в конфигурации
3. Проверить логи `check_proactive_triggers_task`

### Quick replies не отображаются
1. Проверить, определён ли `last_journey_stage` у пользователя
2. Проверить, что `UIManager.create_quick_replies()` вызывается
3. Проверить логи на ошибки форматирования

## Следующие шаги

1. ✅ Создать миграцию БД
2. ✅ Запустить фоновые задачи
3. ✅ Протестировать все компоненты
4. ⚠️ Настроить Redis (опционально)
5. ⚠️ Добавить аналитику и метрики
6. ⚠️ Написать unit тесты
7. ⚠️ Обновить документацию

## Контакты

При возникновении вопросов или проблем:
- Проверить логи в `relove_bot/logs/`
- Проверить статус фоновых задач
- Проверить конфигурацию в БД
