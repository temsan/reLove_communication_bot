# Design Document

## Overview

Завершение разработки reLove Communication Bot с полной интеграцией всех компонентов: персистентность сессий, ротация профилей, путь героя Кэмпбелла, провокативный стиль Наташи, админ-панель и дашборд. Система должна автоматически поддерживать актуальность данных пользователей и обеспечивать максимальную конверсию в платные потоки.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Telegram Bot API                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    aiogram Bot (3.3.0)                          │
├─────────────────┬─────────────────┬─────────────────┬───────────┤
│   Handlers      │   Middleware    │   Services      │   States  │
│ • Provocative   │ • Session Check │ • Profile       │ • FSM     │
│ • Diagnostic    │ • Profile Update│ • LLM           │ • Redis   │
│ • Common        │ • Logging       │ • Telegram      │           │
│ • Admin         │                 │ • Journey       │           │
└─────────────────┴─────────────────┴─────────────────┴───────────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   Background    │    │   Web Dashboard │
│   Database      │    │   Tasks         │    │   (aiohttp)     │
│ • Users         │    │ • Profile Rotate│    │ • Admin Panel   │
│ • Sessions      │    │ • Archive Logs  │    │ • Analytics     │
│ • Logs          │    │ • Update Stages │    │ • User Gallery  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   LLM Service   │    │  Telegram API   │    │   Monitoring    │
│ • OpenAI/Groq   │    │  (Telethon)     │    │ • Logs          │
│ • Retry Logic   │    │ • Get Posts     │    │ • Metrics       │
│ • Rate Limiting │    │ • Get Bio       │    │ • Alerts        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow

#### 1. User Message Flow
```
User Message → Handler → Session Check Middleware → Profile Update Middleware
                                                              ↓
                                                    Check last_seen_date
                                                              ↓
                                                    Update last_seen_date
                                                              ↓
                                                    Save to UserActivityLog
                                                              ↓
                                                    Check profile age (7 days)
                                                              ↓
                                                    If old → Queue background update
                                                              ↓
                                                    Process message in session
```

#### 2. Profile Rotation Flow
```
Background Task (24h) → Get active users (last 30 days)
                                ↓
                        Filter by profile age (>7 days)
                                ↓
                        Process in batches (10 users)
                                ↓
                        For each user:
                          - Get last 50 logs
                          - Get Telegram posts
                          - Send to LLM
                          - Update psychological_summary
                          - Update streams
                          - Update markers['profile_updated_at']
                                ↓
                        Log statistics
```

#### 3. Session Persistence Flow
```
User starts session → Create UserSession in DB
                                ↓
                        Set session_type, state
                                ↓
                        Save conversation_history
                                ↓
User sends message → Update conversation_history
                                ↓
                        Update identified_patterns
                                ↓
Session ends → Set is_active=False
                                ↓
                Update User.metaphysical_profile
                                ↓
                Update User.last_journey_stage
                                ↓
                Set completed_at
```

## Components and Interfaces

### 1. Middleware Components

#### SessionCheckMiddleware
```python
class SessionCheckMiddleware(BaseMiddleware):
    """Проверяет наличие активных сессий перед обработкой команд"""
    
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        session = await get_active_session(user_id)
        
        if session and is_new_session_command(event):
            # Предложить завершить текущую сессию
            await offer_session_completion(event, session)
            return
        
        data['active_session'] = session
        return await handler(event, data)
```

#### ProfileUpdateMiddleware
```python
class ProfileUpdateMiddleware(BaseMiddleware):
    """Обновляет профиль пользователя при каждом контакте"""
    
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        
        # Обновляем last_seen_date
        await update_last_seen(user_id)
        
        # Сохраняем в UserActivityLog
        await save_activity_log(user_id, event)
        
        # Проверяем возраст профиля
        profile_age = await get_profile_age(user_id)
        if profile_age > timedelta(days=7):
            # Запускаем фоновое обновление
            asyncio.create_task(update_profile_background(user_id))
        
        return await handler(event, data)
```

### 2. Service Components

#### ProfileRotationService
```python
class ProfileRotationService:
    """Сервис для ротации профилей пользователей"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = llm_service
        self.telegram_service = telegram_service
    
    async def rotate_profiles(self):
        """Ротация профилей активных пользователей"""
        # Получаем пользователей для обновления
        users = await self.get_users_for_rotation()
        
        # Обрабатываем пачками
        for batch in batched(users, 10):
            await self.process_batch(batch)
            await asyncio.sleep(5)  # Пауза между пачками
        
        # Логируем статистику
        await self.log_rotation_stats()
    
    async def get_users_for_rotation(self) -> List[User]:
        """Получает пользователей для ротации"""
        # last_seen_date в последние 30 дней
        # psychological_summary старше 7 дней
        ...
    
    async def process_batch(self, users: List[User]):
        """Обрабатывает пачку пользователей"""
        for user in users:
            try:
                await self.update_user_profile(user)
            except Exception as e:
                logger.error(f"Error updating user {user.id}: {e}")
    
    async def update_user_profile(self, user: User):
        """Обновляет профиль пользователя"""
        # Получаем последние логи
        logs = await self.get_recent_logs(user.id, limit=50)
        
        # Получаем посты из Telegram
        posts = await self.telegram_service.get_user_posts(user.id)
        
        # Формируем промпт для LLM
        prompt = self.build_update_prompt(user, logs, posts)
        
        # Получаем обновлённый анализ
        analysis = await self.llm_service.analyze_profile(prompt)
        
        # Обновляем профиль
        await self.save_updated_profile(user, analysis)
```

#### SessionPersistenceService
```python
class SessionPersistenceService:
    """Сервис для работы с персистентными сессиями"""
    
    async def create_session(
        self, 
        user_id: int, 
        session_type: str
    ) -> UserSession:
        """Создаёт новую сессию"""
        session = UserSession(
            user_id=user_id,
            session_type=session_type,
            conversation_history=[],
            is_active=True
        )
        self.session.add(session)
        await self.session.commit()
        return session
    
    async def update_session(
        self, 
        session_id: int, 
        message: Dict[str, str]
    ):
        """Обновляет историю сессии"""
        session = await self.get_session(session_id)
        session.conversation_history.append(message)
        session.question_count += 1
        await self.session.commit()
    
    async def complete_session(self, session_id: int):
        """Завершает сессию"""
        session = await self.get_session(session_id)
        session.is_active = False
        session.completed_at = datetime.now()
        
        # Обновляем User модель
        await self.update_user_from_session(session)
        
        await self.session.commit()
    
    async def restore_active_sessions(self) -> Dict[int, UserSession]:
        """Восстанавливает активные сессии при перезапуске"""
        result = await self.session.execute(
            select(UserSession).where(UserSession.is_active == True)
        )
        sessions = result.scalars().all()
        return {s.user_id: s for s in sessions}
```

#### JourneyTrackingService
```python
class JourneyTrackingService:
    """Сервис для отслеживания пути героя"""
    
    async def analyze_journey_stage(
        self, 
        user_id: int, 
        conversation_history: List[Dict]
    ) -> Optional[JourneyStageEnum]:
        """Анализирует текущий этап пути героя"""
        # Получаем текущий этап
        user = await self.get_user(user_id)
        current_stage = user.last_journey_stage
        
        # Формируем промпт для LLM
        prompt = self.build_stage_analysis_prompt(
            current_stage, 
            conversation_history
        )
        
        # Анализируем через LLM
        new_stage = await self.llm_service.analyze_stage(prompt)
        
        return new_stage
    
    async def update_journey_stage(
        self, 
        user_id: int, 
        new_stage: JourneyStageEnum
    ):
        """Обновляет этап пути героя"""
        # Обновляем User
        user = await self.get_user(user_id)
        old_stage = user.last_journey_stage
        user.last_journey_stage = new_stage
        
        # Создаём запись в JourneyProgress
        progress = JourneyProgress(
            user_id=user_id,
            current_stage=new_stage,
            stage_start_time=datetime.now()
        )
        
        # Добавляем старый этап в completed_stages
        if old_stage:
            progress.completed_stages = [old_stage]
        
        self.session.add(progress)
        await self.session.commit()
```

#### AdminBroadcastService
```python
class AdminBroadcastService:
    """Сервис для админ-рассылки"""
    
    async def broadcast_message(
        self, 
        message: str, 
        criteria: Dict[str, Any]
    ) -> Dict[str, int]:
        """Отправляет рассылку по критериям"""
        # Получаем пользователей по критериям
        users = await self.get_users_by_criteria(criteria)
        
        stats = {
            'sent': 0,
            'errors': 0,
            'blocked': 0
        }
        
        # Отправляем с rate limiting (30 msg/sec)
        rate_limiter = RateLimiter(30, 1)
        
        for user in users:
            async with rate_limiter:
                try:
                    await self.bot.send_message(user.id, message)
                    stats['sent'] += 1
                except BotBlocked:
                    await self.mark_user_inactive(user.id)
                    stats['blocked'] += 1
                except Exception as e:
                    logger.error(f"Error sending to {user.id}: {e}")
                    stats['errors'] += 1
        
        return stats
    
    async def get_users_by_criteria(
        self, 
        criteria: Dict[str, Any]
    ) -> List[User]:
        """Получает пользователей по критериям"""
        query = select(User).where(User.is_active == True)
        
        # Фильтр по полу
        if 'gender' in criteria:
            query = query.where(User.gender == criteria['gender'])
        
        # Фильтр по этапу пути героя
        if 'journey_stage' in criteria:
            query = query.where(
                User.last_journey_stage == criteria['journey_stage']
            )
        
        # Фильтр по потокам
        if 'streams' in criteria:
            for stream in criteria['streams']:
                query = query.where(
                    User.streams.contains([stream])
                )
        
        # Фильтр по маркерам
        if 'markers' in criteria:
            for key, value in criteria['markers'].items():
                query = query.where(
                    User.markers[key].astext == str(value)
                )
        
        result = await self.session.execute(query)
        return result.scalars().all()
```

### 3. Background Tasks

#### ProfileRotationTask
```python
async def profile_rotation_task():
    """Фоновая задача ротации профилей"""
    while True:
        try:
            logger.info("Starting profile rotation...")
            
            async with AsyncSessionFactory() as session:
                service = ProfileRotationService(session)
                await service.rotate_profiles()
            
            logger.info("Profile rotation completed")
        except Exception as e:
            logger.error(f"Error in profile rotation: {e}")
        
        # Ждём 24 часа
        await asyncio.sleep(86400)
```

#### LogArchiveTask
```python
async def log_archive_task():
    """Фоновая задача архивации логов"""
    while True:
        try:
            logger.info("Starting log archiving...")
            
            async with AsyncSessionFactory() as session:
                # Архивируем логи старше 90 дней
                cutoff_date = datetime.now() - timedelta(days=90)
                
                # Получаем пользователей с >1000 логов
                users = await get_users_with_many_logs(session)
                
                for user_id in users:
                    await archive_old_logs(session, user_id, cutoff_date)
            
            logger.info("Log archiving completed")
        except Exception as e:
            logger.error(f"Error in log archiving: {e}")
        
        # Ждём 7 дней
        await asyncio.sleep(604800)
```

## Data Models

### Updated User Model
```python
class User(Base):
    # Существующие поля
    id: Mapped[int]
    username: Mapped[Optional[str]]
    first_name: Mapped[Optional[str]]
    last_name: Mapped[Optional[str]]
    registration_date: Mapped[datetime]
    last_seen_date: Mapped[datetime]  # Обновляется при каждом контакте
    gender: Mapped[Optional[GenderEnum]]
    
    # Профиль
    psychological_summary: Mapped[Optional[str]]  # Обновляется каждые 7 дней
    profile_summary: Mapped[Optional[str]]
    photo_jpeg: Mapped[Optional[bytes]]
    
    # Метафизика и путь героя
    metaphysical_profile: Mapped[Optional[Dict[str, Any]]]
    last_journey_stage: Mapped[Optional[JourneyStageEnum]]
    
    # Потоки и маркеры
    streams: Mapped[Optional[List[str]]]
    markers: Mapped[Optional[Dict[str, Any]]]  # Включая 'profile_updated_at'
    
    # Конверсия
    has_started_journey: Mapped[bool]
    has_completed_journey: Mapped[bool]
    has_visited_platform: Mapped[bool]
    has_purchased_flow: Mapped[bool]
    
    # Статус
    is_admin: Mapped[bool]
    is_active: Mapped[bool]
```

### UserSession Model (Already exists)
```python
class UserSession(Base):
    id: Mapped[int]
    user_id: Mapped[int]
    session_type: Mapped[str]  # 'provocative', 'diagnostic', 'journey'
    state: Mapped[Optional[str]]
    conversation_history: Mapped[List[Dict[str, str]]]
    identified_patterns: Mapped[Optional[List[str]]]
    core_issue: Mapped[Optional[str]]
    question_count: Mapped[int]
    metaphysical_profile: Mapped[Optional[Dict[str, Any]]]
    core_trauma: Mapped[Optional[Dict[str, Any]]]
    session_data: Mapped[Optional[Dict[str, Any]]]
    is_active: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    completed_at: Mapped[Optional[datetime]]
```

### New: UserActivityLogArchive Model
```python
class UserActivityLogArchive(Base):
    """Архив старых логов активности"""
    __tablename__ = "user_activity_logs_archive"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    activity_type: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
```

## Error Handling

### Retry Logic for LLM
```python
class LLMServiceWithRetry:
    """LLM сервис с retry логикой"""
    
    async def analyze_with_retry(
        self, 
        prompt: str, 
        max_retries: int = 2
    ) -> str:
        """Анализ с повторными попытками"""
        for attempt in range(max_retries + 1):
            try:
                result = await self.llm_service.analyze(prompt)
                return result
            except Exception as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Экспоненциальная задержка
                    logger.warning(
                        f"LLM attempt {attempt + 1} failed, "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"LLM failed after {max_retries} retries: {e}")
                    raise
```

### Session Recovery
```python
async def recover_session_on_error(
    user_id: int, 
    session_id: int, 
    error: Exception
):
    """Восстанавливает сессию после ошибки"""
    try:
        # Сохраняем текущее состояние
        async with AsyncSessionFactory() as db_session:
            session = await db_session.get(UserSession, session_id)
            if session:
                session.session_data = session.session_data or {}
                session.session_data['last_error'] = str(error)
                session.session_data['error_timestamp'] = datetime.now().isoformat()
                await db_session.commit()
        
        # Уведомляем пользователя
        await bot.send_message(
            user_id,
            "Временные технические проблемы. Ваш прогресс сохранён, "
            "можете продолжить позже."
        )
    except Exception as e:
        logger.error(f"Error recovering session: {e}")
```

## Testing Strategy

### Unit Tests
- ProfileRotationService.update_user_profile()
- SessionPersistenceService.create_session()
- JourneyTrackingService.analyze_journey_stage()
- AdminBroadcastService.get_users_by_criteria()

### Integration Tests
- Полный цикл ротации профиля
- Создание и восстановление сессии
- Обновление этапа пути героя
- Рассылка с фильтрацией

### End-to-End Tests
- Пользователь начинает провокативную сессию → профиль обновляется
- Фоновая ротация → профили актуализируются
- Админ отправляет рассылку → пользователи получают сообщения

## Performance Considerations

### Database Optimization
- Индексы на last_seen_date, last_journey_stage, is_active
- Партиционирование UserActivityLog по timestamp
- Архивация старых логов в отдельную таблицу

### Rate Limiting
- LLM запросы: 10 req/sec
- Telegram API: 30 msg/sec для рассылки
- Фоновая ротация: пачками по 10 с паузами 5 сек

### Caching
- Активные сессии в памяти (восстановление из БД при перезапуске)
- Профили пользователей кэшируются на 1 час
- Результаты LLM анализа кэшируются по хэшу промпта

## Security Considerations

- Админ-команды доступны только пользователям с is_admin=True
- Рассылка логируется с указанием администратора
- Персональные данные (psychological_summary) не передаются третьим лицам
- LLM промпты не содержат PII (только обезличенные данные)

## Deployment Strategy

### Phase 1: Core Infrastructure (Week 1)
- Middleware для проверки сессий и обновления профилей
- SessionPersistenceService
- Миграция БД (UserActivityLogArchive)

### Phase 2: Profile Rotation (Week 2)
- ProfileRotationService
- Фоновые задачи (rotation, archiving)
- Обновление fill_profiles.py

### Phase 3: Journey Integration (Week 3)
- JourneyTrackingService
- Интеграция с провокативной сессией
- Обновление промптов

### Phase 4: Admin & Dashboard (Week 4)
- AdminBroadcastService
- Обновление веб-дашборда
- Тестирование и оптимизация

## Monitoring and Logging

### Metrics to Track
- Профили обновлены за день
- Активные сессии
- Конверсия по этапам пути героя
- Ошибки LLM запросов
- Скорость рассылки

### Alerts
- Ошибка фоновой ротации
- LLM недоступен >5 минут
- Рассылка заблокирована >10% пользователей
- БД недоступна

### Logging
- Все обновления профилей
- Все переходы по этапам пути героя
- Все рассылки (кто, когда, кому, результат)
- Все ошибки с полным traceback
