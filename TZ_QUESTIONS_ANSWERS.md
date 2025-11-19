# ❓ Ответы на вопросы из ТЗ

## Вопрос 1: Сохранять сгенерированные комментарии в БД бот-анализа или в БД личностей тг аккаунтов комментатора?

**Ответ:** В **единую БД** с отдельной таблицей `GeneratedComment`:

```python
class GeneratedComment(Base):
    __tablename__ = "generated_comments"
    
    id: int  # primary key
    post_id: int  # FK на TelegramPost
    account_id: int  # FK на CommentatorAccount
    text: str  # сгенерированный текст
    status: str  # pending, sent, failed, deleted
    created_at: datetime
    sent_at: datetime
    failed_reason: str  # если status=failed
    engagement_metrics: JSON  # likes, replies, views (если отправлен)
```

**Логика:**
- Комментарий связан с постом (для анализа эффективности)
- Комментарий связан с аккаунтом (для анализа личности)
- История всех комментариев в одном месте
- Легко анализировать: какие комментарии работают, какие аккаунты эффективнее

---

## Вопрос 2: Как и какие данные мы будем сохранять для корректной работы блока комментаторов и сколько БД нам потребуется?

**Ответ:** **Одна БД PostgreSQL** с расширенной схемой.

### Данные для комментаторов:

```python
# 1. Каналы
class TelegramChannel(Base):
    id: int  # channel_id
    title: str
    description: str
    username: str
    members_count: int
    is_active: bool
    last_checked: datetime
    monitoring_interval: int  # в минутах
    
# 2. Посты
class TelegramPost(Base):
    id: int  # message_id
    channel_id: int  # FK
    text: str
    media_urls: JSON  # список URL медиа
    summary: JSON  # {main_idea, keywords, tone, content_type}
    created_at: datetime
    engagement: JSON  # {views, likes, comments}
    
# 3. Аккаунты комментаторов
class CommentatorAccount(Base):
    id: int
    phone: str  # зашифрована
    username: str
    first_name: str
    bio: str
    personality: JSON  # {style, tone, interests, vocabulary}
    is_active: bool
    created_at: datetime
    last_used: datetime
    
# 4. Сгенерированные комментарии
class GeneratedComment(Base):
    id: int
    post_id: int  # FK
    account_id: int  # FK
    text: str
    status: str  # pending, sent, failed
    created_at: datetime
    sent_at: datetime
    
# 5. Расписание
class CommentSchedule(Base):
    id: int
    account_id: int  # FK
    channel_id: int  # FK
    comments_per_day: int
    start_time: str  # "09:00"
    end_time: str  # "23:00"
    is_active: bool
    
# 6. Ответы в личку
class DirectMessage(Base):
    id: int
    account_id: int  # FK (от кого)
    user_id: int  # FK (кому)
    text: str
    direction: str  # incoming, outgoing
    created_at: datetime
    is_read: bool
```

### Сколько БД?
- **1 основная БД** (PostgreSQL) для всех данных
- **Опционально:** Redis для кэша (сессии, временные данные)
- **Опционально:** Qdrant для поиска похожих пользователей (если нужно)

**Рекомендация:** Начать с 1 PostgreSQL, добавить Redis если будут проблемы с производительностью.

---

## Вопрос 3: Сколько и какие именно таблицы понадобятся в БД?

**Ответ:** **18-20 таблиц** (минимум для полной функциональности):

### Основные (User, Chat, Activity):
1. `users` — пользователи
2. `chats` — чаты/группы
3. `user_activity_log` — логи активности

### Комментатор:
4. `telegram_channels` — каналы
5. `telegram_posts` — посты
6. `commentator_accounts` — аккаунты комментаторов
7. `account_personalities` — личности аккаунтов
8. `generated_comments` — сгенерированные комментарии
9. `comment_schedules` — расписание комментариев
10. `direct_messages` — личные сообщения

### Продажи:
11. `sales_scripts` — скрипты продаж
12. `script_versions` — версии скриптов
13. `script_triggers` — триггеры скриптов
14. `client_conversations` — диалоги продаж
15. `conversation_messages` — сообщения в диалогах

### Группы учеников:
16. `education_groups` — группы обучения
17. `student_bots` — боты-ученики в группах
18. `group_messages` — сообщения в группах

### Управление аккаунтами:
19. `telegram_account_sessions` — сессии Telethon
20. `account_security_logs` — логи безопасности

### Диагностика (уже есть):
21. `diagnostic_results` — результаты диагностики
22. `journey_progress` — прогресс пути героя
23. `user_sessions` — сессии пользователей

**Итого: ~23 таблицы**

---

## Вопрос 4: Как реализовать оптимальную архитектуру хранения данных?

**Ответ:** **Многоуровневая архитектура:**

```
┌─────────────────────────────────────────┐
│         Telegram API (Telethon)         │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│      Services Layer (бизнес-логика)     │
│  ChannelMonitorService                  │
│  CommentGenerationService               │
│  SalesConversationService               │
│  EducationGroupService                  │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│      Repository Layer (доступ к БД)     │
│  ChannelRepository                      │
│  PostRepository                         │
│  CommentatorRepository                  │
│  ScriptRepository                       │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│    Database Layer (PostgreSQL)          │
│  - Основные таблицы                     │
│  - Индексы на часто используемые поля  │
│  - Партиционирование больших таблиц    │
└─────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│      Cache Layer (Redis)                │
│  - Сессии аккаунтов                     │
│  - Кэш промптов                         │
│  - Временные данные                     │
└─────────────────────────────────────────┘
```

### Оптимизация:
1. **Индексы:**
   - `user_id` на всех таблицах с пользователями
   - `channel_id` на таблице постов
   - `account_id` на таблице комментариев
   - `status` на таблицах с состояниями

2. **Партиционирование:**
   - `telegram_posts` по `channel_id`
   - `generated_comments` по `created_at` (месячные партиции)
   - `user_activity_log` по `created_at` (месячные партиции)

3. **Кэширование:**
   - Личности аккаунтов в Redis (TTL 1 час)
   - Скрипты в Redis (TTL 24 часа)
   - Сессии Telethon в Redis (TTL 7 дней)

4. **Асинхронность:**
   - Все операции через SQLAlchemy async
   - Пулинг соединений (pool_size=20, max_overflow=40)
   - Batch операции для массовых вставок

---

## Вопрос 5: Как лучше организовать логирование и трекинг сессий?

**Ответ:** **Трёхуровневое логирование:**

### Уровень 1: Логи приложения
```python
# relove_bot/logging_config.py
import logging

logger = logging.getLogger(__name__)

# Логируем:
# - Начало/конец операций
# - Ошибки и исключения
# - Важные события (создание группы, отправка комментария)
```

### Уровень 2: Трекинг сессий в БД
```python
class SessionLog(Base):
    __tablename__ = "session_logs"
    
    id: int
    user_id: int
    session_type: str  # "comment", "sales", "education"
    start_time: datetime
    end_time: datetime
    status: str  # "active", "completed", "failed"
    metadata: JSON  # {messages_count, errors, etc}
    
class OperationLog(Base):
    __tablename__ = "operation_logs"
    
    id: int
    operation_type: str  # "generate_comment", "send_message"
    user_id: int
    account_id: int
    status: str  # "success", "failed"
    error_message: str
    duration_ms: int
    created_at: datetime
```

### Уровень 3: Аналитика
```python
# Дашборд показывает:
# - Активные сессии
# - Успешность операций
# - Время выполнения
# - Ошибки и их причины
```

### Реализация:
```python
# relove_bot/services/logging_service.py
class LoggingService:
    async def log_session_start(user_id: int, session_type: str)
    async def log_session_end(user_id: int, session_type: str, status: str)
    async def log_operation(operation_type: str, status: str, duration: int, error: str = None)
    async def get_session_stats(user_id: int) -> dict
    async def get_operation_stats() -> dict
```

---

## Вопрос 6: Как реализовать переключение логики между «человеческим ответом» и шаблоном?

**Ответ:** **Система стратегий с LLM анализом:**

```python
class StrategySelectorService:
    async def select_strategy(message: str, user: User) -> str:
        """
        Возвращает: "script_80" или "free_20"
        """
        # 1. Анализируем сообщение через LLM
        analysis = await llm_service.analyze_message(message, user)
        
        # 2. Определяем, насколько сообщение подходит под скрипт
        script_fit_score = analysis.get("script_fit_score", 0.5)  # 0-1
        
        # 3. Выбираем стратегию
        if script_fit_score > 0.7:
            return "script_80"  # 80% скрипт, 20% свободный
        else:
            return "free_20"  # 20% скрипт, 80% свободный
            
class SalesConversationService:
    async def generate_response(conversation: ClientConversation, message: str) -> str:
        # 1. Выбираем стратегию
        strategy = await strategy_selector.select_strategy(message, conversation.user)
        
        # 2. Если script_80 — используем скрипт
        if strategy == "script_80":
            script_response = await self.get_script_response(conversation.script, message)
            # Адаптируем под эмоциональный тон
            response = await llm_service.adapt_response(script_response, message)
        
        # 3. Если free_20 — свободный диалог с элементами скрипта
        else:
            response = await llm_service.generate_free_response(
                message=message,
                user=conversation.user,
                script_hints=conversation.script.get("hints", [])
            )
        
        return response
```

### Логика выбора:
- **script_80:** Сообщение четко подходит под скрипт (вопрос о цене, возражение, интерес)
- **free_20:** Сообщение не подходит под скрипт (личная история, эмоции, отвлечение)

---

## Вопрос 7: Будет ли возможность редактировать шаблоны сообщений/ответов прямо из панели?

**Ответ:** **Да, полностью.**

### Редактор скриптов в админ-панели:

```python
# relove_bot/admin/scripts.py
@scripts_bp.route('/scripts/<int:script_id>/edit', methods=['GET', 'POST'])
def edit_script(script_id):
    script = ScriptRepository.get_by_id(script_id)
    
    if request.method == 'POST':
        # 1. Обновляем скрипт в БД
        script.content = request.json['content']
        script.version += 1
        db.session.commit()
        
        # 2. Инвалидируем кэш
        cache.delete(f"script_{script_id}")
        
        # 3. Логируем изменение
        await logging_service.log_operation(
            "script_update",
            "success",
            script_id=script_id,
            version=script.version
        )
        
        return {"status": "ok", "version": script.version}
    
    return render_template('scripts/edit.html', script=script)
```

### Функции редактора:
- ✅ Редактирование JSON/YAML
- ✅ Предпросмотр (как будет выглядеть ответ)
- ✅ История версий (откат к старой версии)
- ✅ Тестирование (отправить тестовое сообщение)
- ✅ Горячая перезагрузка (без перезапуска бота)
- ✅ Валидация синтаксиса

### Горячая перезагрузка:
```python
# relove_bot/services/script_service.py
class ScriptService:
    _scripts_cache = {}
    
    async def load_script(script_id: int) -> dict:
        # 1. Проверяем кэш
        if script_id in self._scripts_cache:
            return self._scripts_cache[script_id]
        
        # 2. Загружаем из БД
        script = await ScriptRepository.get_by_id(script_id)
        
        # 3. Кэшируем
        self._scripts_cache[script_id] = script.content
        
        return script.content
    
    async def invalidate_cache(script_id: int):
        """Вызывается при обновлении скрипта"""
        if script_id in self._scripts_cache:
            del self._scripts_cache[script_id]
```

---

## Вопрос 8: Как обеспечить отказоустойчивость при массовой генерации и отправке комментариев?

**Ответ:** **Система очередей с retry логикой:**

```python
# relove_bot/services/comment_scheduler_service.py
class CommentSchedulerService:
    async def send_scheduled_comments():
        """Отправляет комментарии с обработкой ошибок"""
        
        # 1. Получаем комментарии со статусом "pending"
        comments = await CommentRepository.get_pending(limit=100)
        
        for comment in comments:
            try:
                # 2. Отправляем комментарий
                await self.send_comment(comment)
                
                # 3. Обновляем статус
                comment.status = "sent"
                comment.sent_at = datetime.now()
                
            except TelegramAPIError as e:
                # 4. Обработка ошибок Telegram
                comment.retry_count = (comment.retry_count or 0) + 1
                
                if comment.retry_count < 3:
                    # Повторим позже
                    comment.status = "pending"
                    comment.next_retry = datetime.now() + timedelta(minutes=5)
                else:
                    # Слишком много попыток
                    comment.status = "failed"
                    comment.failed_reason = str(e)
                    
            except Exception as e:
                # 5. Неожиданная ошибка
                logger.error(f"Unexpected error: {e}")
                comment.status = "failed"
                comment.failed_reason = str(e)
            
            finally:
                # 6. Сохраняем в БД
                await db.session.commit()
                
                # 7. Rate limiting (30 msg/sec для Telegram)
                await asyncio.sleep(0.1)
```

### Отказоустойчивость:
1. **Retry логика:** до 3 попыток с экспоненциальной задержкой
2. **Rate limiting:** 30 сообщений в секунду (лимит Telegram)
3. **Batch обработка:** обрабатываем по 100 комментариев за раз
4. **Логирование:** все ошибки логируются
5. **Мониторинг:** дашборд показывает статус отправки
6. **Graceful shutdown:** при остановке бота сохраняем состояние

---

## Вопрос 9: Как хранить сценарии (лучше в БД или в JSON-файлах)?

**Ответ:** **В БД с опциональным экспортом в JSON.**

### Структура:
```python
class SalesScript(Base):
    __tablename__ = "sales_scripts"
    
    id: int
    name: str  # "Скрипт №1 - Продажи"
    description: str
    content: JSON  # {steps, triggers, responses}
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: int  # user_id
    
class ScriptVersion(Base):
    __tablename__ = "script_versions"
    
    id: int
    script_id: int  # FK
    version: int
    content: JSON
    created_at: datetime
    created_by: int
    change_description: str
```

### Преимущества БД:
- ✅ Версионирование встроено
- ✅ Горячая перезагрузка
- ✅ История изменений
- ✅ Откат к старой версии
- ✅ Аудит (кто и когда изменил)

### Экспорт в JSON:
```python
# Для резервной копии или обмена
async def export_script(script_id: int) -> str:
    script = await ScriptRepository.get_by_id(script_id)
    return json.dumps(script.content, indent=2, ensure_ascii=False)

async def import_script(json_content: str) -> SalesScript:
    content = json.loads(json_content)
    script = SalesScript(content=content, version=1)
    await db.session.add(script)
    await db.session.commit()
    return script
```

---

## Вопрос 10: Как организовать обновление логики без остановки бота?

**Ответ:** **Горячая перезагрузка через кэш и сигналы:**

```python
# relove_bot/services/hot_reload_service.py
class HotReloadService:
    _reload_signal = asyncio.Event()
    
    async def watch_for_changes():
        """Следит за изменениями в БД"""
        while True:
            # 1. Проверяем, есть ли новые версии скриптов
            new_scripts = await ScriptRepository.get_updated_since(last_check_time)
            
            if new_scripts:
                # 2. Инвалидируем кэш
                for script in new_scripts:
                    await ScriptService.invalidate_cache(script.id)
                
                # 3. Логируем
                logger.info(f"Hot reload: {len(new_scripts)} scripts updated")
                
                # 4. Отправляем сигнал
                self._reload_signal.set()
            
            # 5. Проверяем каждые 10 секунд
            await asyncio.sleep(10)
    
    async def wait_for_reload():
        """Ждет сигнала перезагрузки"""
        await self._reload_signal.wait()
        self._reload_signal.clear()
```

### Использование:
```python
# relove_bot/handlers/sales_handler.py
async def handle_message(message: Message, session: AsyncSession):
    # 1. Получаем скрипт (из кэша или БД)
    script = await ScriptService.load_script(script_id)
    
    # 2. Используем скрипт
    response = await generate_response(script, message)
    
    # 3. Если произошла перезагрузка, скрипт автоматически обновится
    # при следующем вызове load_script()
```

### Процесс:
1. Администратор редактирует скрипт в админ-панели
2. Скрипт сохраняется в БД с новой версией
3. HotReloadService обнаруживает изменение
4. Кэш инвалидируется
5. При следующем использовании скрипта загружается новая версия
6. **Бот продолжает работать без перезапуска**

