# Requirements Document

## Introduction

Завершение разработки кодовой базы проекта reLove Communication Bot с полной интеграцией профилей пользователей из БД, пути героя Кэмпбелла и провокативного стиля Наташи Волкош. Цель — создать целостную систему, где все компоненты работают синхронно для максимальной эффективности привлечения пользователей на платные потоки.

## Glossary

- **Bot System**: Telegram-бот reLove Communication Bot
- **User Profile**: Профиль пользователя в БД (psychological_summary, metaphysical_profile, streams, markers)
- **Hero Journey**: Путь героя Кэмпбелла (12 этапов трансформации)
- **Provocative Session**: Провокативная сессия в стиле Наташи Волкош
- **Session Persistence**: Сохранение сессий в БД (UserSession модель)
- **Profile Service**: Сервис для работы с профилями пользователей
- **LLM Service**: Сервис для работы с языковыми моделями
- **Admin Broadcast**: Система рассылки сообщений администратором
- **Conversion Tracking**: Отслеживание конверсии пользователей
- **State Conflict Handler**: Обработчик конфликтов состояний FSM

## Requirements

### Requirement 1: Персистентность сессий

**User Story:** Как пользователь, я хочу, чтобы мои сессии с ботом сохранялись и восстанавливались после перезапуска бота, чтобы не терять прогресс в диалоге.

#### Acceptance Criteria

1. WHEN пользователь начинает провокативную сессию через /natasha, THE Bot System SHALL создать запись UserSession в БД с типом 'provocative'
2. WHEN пользователь начинает гибкую диагностику через /diagnostic, THE Bot System SHALL создать запись UserSession в БД с типом 'diagnostic'
3. WHEN пользователь отправляет сообщение в активной сессии, THE Bot System SHALL обновить conversation_history в UserSession
4. WHEN бот перезапускается, THE Bot System SHALL восстановить активные сессии из БД для всех пользователей
5. WHEN сессия завершается, THE Bot System SHALL установить is_active=False и заполнить completed_at

### Requirement 2: Интеграция профилей с сессиями

**User Story:** Как система, я хочу использовать данные профиля пользователя (psychological_summary, streams, markers) в провокативных сессиях и диагностике, чтобы персонализировать диалог.

#### Acceptance Criteria

1. WHEN провокативная сессия начинается, THE Bot System SHALL загрузить psychological_summary пользователя и передать его в LLM контекст
2. WHEN LLM генерирует ответ, THE Bot System SHALL учитывать текущий last_journey_stage пользователя
3. WHEN сессия завершается, THE Bot System SHALL обновить metaphysical_profile в User модели на основе данных из UserSession
4. WHEN сессия завершается, THE Bot System SHALL обновить last_journey_stage в User модели
5. WHEN бот анализирует готовность к потокам, THE Bot System SHALL использовать streams из User модели

### Requirement 3: Админ-рассылка с фильтрацией

**User Story:** Как администратор, я хочу отправлять рассылки пользователям с фильтрацией по критериям (пол, этап пути героя, потоки, маркеры), чтобы таргетировать сообщения.

#### Acceptance Criteria

1. WHEN администратор вводит критерии рассылки, THE Bot System SHALL распарсить критерии в SQLAlchemy фильтры
2. WHEN администратор запускает рассылку, THE Bot System SHALL получить список пользователей из БД по критериям
3. WHEN рассылка выполняется, THE Bot System SHALL отправлять не более 30 сообщений в секунду
4. IF пользователь заблокировал бота, THEN THE Bot System SHALL пометить пользователя как is_active=False
5. WHEN рассылка завершается, THE Bot System SHALL показать статистику (отправлено, ошибки, заблокировано)

### Requirement 4: Обработка конфликтов состояний

**User Story:** Как пользователь, я хочу, чтобы бот корректно обрабатывал ситуации, когда я пытаюсь начать новую сессию во время активной, чтобы избежать путаницы.

#### Acceptance Criteria

1. WHEN пользователь начинает новую сессию, THE Bot System SHALL проверить наличие активных сессий в БД
2. IF активная сессия существует, THEN THE Bot System SHALL предложить завершить текущую сессию или продолжить её
3. WHEN пользователь отправляет обычное сообщение во время активной сессии, THE Bot System SHALL обработать его в контексте сессии
4. WHEN пользователь выбирает завершить текущую сессию, THE Bot System SHALL сохранить результаты и закрыть сессию
5. WHEN пользователь выбирает продолжить сессию, THE Bot System SHALL восстановить контекст и продолжить диалог

### Requirement 5: Анализ готовности с историей

**User Story:** Как система, я хочу анализировать готовность пользователя к потокам на основе истории сообщений (UserActivityLog) и профиля, чтобы давать точные рекомендации.

#### Acceptance Criteria

1. WHEN пользователь запрашивает /analyze_readiness, THE Bot System SHALL загрузить последние 50 записей из UserActivityLog
2. WHEN анализ выполняется, THE Bot System SHALL передать LLM историю сообщений и psychological_summary
3. WHEN LLM анализирует готовность, THE Bot System SHALL получить оценку готовности для каждого потока (0-100%)
4. WHEN анализ завершён, THE Bot System SHALL показать топ-3 рекомендованных потока с обоснованием
5. WHEN пользователь выбирает поток, THE Bot System SHALL сохранить выбор в markers['interested_stream']

### Requirement 6: Удаление дублирования диагностики

**User Story:** Как разработчик, я хочу удалить устаревший модуль diagnostic.py, чтобы избежать путаницы и дублирования функционала.

#### Acceptance Criteria

1. THE Bot System SHALL удалить файл relove_bot/handlers/diagnostic.py
2. THE Bot System SHALL удалить команду /start_diagnostic из регистрации обработчиков
3. THE Bot System SHALL оставить только /diagnostic (гибкая LLM-диагностика) и /start_journey (традиционная)
4. THE Bot System SHALL обновить документацию с актуальным списком команд
5. THE Bot System SHALL убедиться, что все ссылки на старый модуль удалены

### Requirement 7: Улучшение обработки ошибок

**User Story:** Как пользователь, я хочу получать понятные сообщения об ошибках, когда что-то идёт не так, чтобы понимать, что делать дальше.

#### Acceptance Criteria

1. WHEN LLM запрос не удаётся, THE Bot System SHALL повторить запрос до 2 раз с экспоненциальной задержкой
2. IF все попытки не удались, THEN THE Bot System SHALL показать пользователю сообщение "Временные технические проблемы, попробуйте позже"
3. WHEN ошибка происходит в сессии, THE Bot System SHALL сохранить текущее состояние сессии в БД
4. WHEN пользователь пытается продолжить после ошибки, THE Bot System SHALL восстановить сессию из БД
5. WHEN критическая ошибка происходит, THE Bot System SHALL отправить уведомление администраторам

### Requirement 8: Отслеживание конверсии

**User Story:** Как администратор, я хочу видеть метрики конверсии пользователей (начало диагностики → завершение → переход на платформу → покупка), чтобы оценивать эффективность бота.

#### Acceptance Criteria

1. WHEN пользователь начинает диагностику, THE Bot System SHALL установить has_started_journey=True
2. WHEN пользователь завершает диагностику, THE Bot System SHALL установить has_completed_journey=True
3. WHEN пользователь переходит по ссылке на платформу, THE Bot System SHALL установить has_visited_platform=True
4. WHEN администратор запрашивает статистику, THE Bot System SHALL показать воронку конверсии
5. WHEN администратор запрашивает детали, THE Bot System SHALL показать конверсию по этапам пути героя

### Requirement 9: Интеграция пути героя с провокативной сессией

**User Story:** Как система, я хочу, чтобы провокативная сессия учитывала текущий этап пути героя пользователя, чтобы адаптировать провокации под его состояние.

#### Acceptance Criteria

1. WHEN провокативная сессия начинается, THE Bot System SHALL определить текущий last_journey_stage пользователя
2. WHEN LLM генерирует провокативный ответ, THE Bot System SHALL передать информацию об этапе в промпт
3. WHEN сессия выявляет новый этап, THE Bot System SHALL обновить last_journey_stage в User модели
4. WHEN сессия завершается, THE Bot System SHALL показать прогресс по этапам пути героя
5. WHEN пользователь запрашивает /my_journey, THE Bot System SHALL показать визуализацию его пути с текущим этапом

### Requirement 10: Ротация и актуализация профиля при каждом контакте

**User Story:** Как система, я хочу автоматически ротировать и актуализировать все данные профиля пользователя (психопрофиль, история, стадия пути героя, логи) при каждом его контакте с ботом, чтобы данные всегда были свежими и релевантными.

#### Acceptance Criteria

1. WHEN пользователь отправляет любое сообщение боту, THE Bot System SHALL обновить last_seen_date в User модели
2. WHEN пользователь отправляет сообщение, THE Bot System SHALL сохранить запись в UserActivityLog с типом 'message' и полным текстом
3. WHEN пользователь отправляет сообщение, THE Bot System SHALL проверить дату последнего обновления psychological_summary
4. IF прошло более 7 дней с последнего обновления psychological_summary, THEN THE Bot System SHALL запустить фоновую задачу актуализации психопрофиля
5. WHEN фоновая задача актуализации выполняется, THE Bot System SHALL получить последние 50 записей из UserActivityLog для анализа динамики
6. WHEN логи получены, THE Bot System SHALL отправить их в LLM вместе со старым psychological_summary для генерации обновлённого анализа
7. WHEN LLM возвращает обновлённый анализ, THE Bot System SHALL обновить psychological_summary с добавлением метки времени обновления
8. WHEN пользователь завершает сессию, THE Bot System SHALL проанализировать conversation_history и обновить last_journey_stage если обнаружен переход на новый этап
9. WHEN last_journey_stage обновляется, THE Bot System SHALL сохранить запись в JourneyProgress с новым этапом и временем перехода
10. WHEN история логов превышает 1000 записей для пользователя, THE Bot System SHALL архивировать старые записи (старше 90 дней) в отдельную таблицу UserActivityLogArchive

### Requirement 11: Фоновая ротация профилей по расписанию

**User Story:** Как система, я хочу автоматически ротировать профили активных пользователей по расписанию, чтобы данные всегда оставались актуальными даже без прямого контакта с ботом.

#### Acceptance Criteria

1. WHEN система запускается, THE Bot System SHALL инициализировать фоновую задачу ротации профилей с интервалом 24 часа
2. WHEN фоновая задача выполняется, THE Bot System SHALL получить список пользователей с last_seen_date в последние 30 дней
3. WHEN список получен, THE Bot System SHALL отфильтровать пользователей, у которых psychological_summary старше 7 дней
4. WHEN пользователи отфильтрованы, THE Bot System SHALL обрабатывать их пачками по 10 пользователей с паузой 5 секунд между пачками
5. WHEN пользователь обрабатывается, THE Bot System SHALL получить его последние сообщения из UserActivityLog и посты из Telegram канала
6. WHEN данные собраны, THE Bot System SHALL отправить их в LLM для обновления psychological_summary и определения streams
7. WHEN обновление завершено, THE Bot System SHALL сохранить метку времени обновления в markers['profile_updated_at']
8. WHEN вся ротация завершена, THE Bot System SHALL записать статистику в лог (обработано, обновлено, ошибок, пропущено)

### Requirement 12: Массовое обновление профилей по требованию

**User Story:** Как администратор, я хочу запускать массовое обновление профилей пользователей из Telegram вручную, чтобы актуализировать psychological_summary и streams для всех активных пользователей по требованию.

#### Acceptance Criteria

1. WHEN администратор запускает скрипт fill_profiles.py, THE Bot System SHALL получить список активных пользователей из БД
2. WHEN профиль обновляется, THE Bot System SHALL получить bio и посты пользователя через Telegram API
3. WHEN данные получены, THE Bot System SHALL отправить их в LLM для анализа
4. WHEN LLM возвращает анализ, THE Bot System SHALL обновить psychological_summary и streams в User модели
5. WHEN обновление завершено, THE Bot System SHALL показать статистику (обновлено, ошибки, пропущено)

### Requirement 13: Дашборд с актуальными данными

**User Story:** Как администратор, я хочу видеть актуальные данные о пользователях в веб-дашборде, чтобы отслеживать активность и эффективность бота.

#### Acceptance Criteria

1. WHEN администратор открывает дашборд, THE Bot System SHALL показать общую статистику (всего пользователей, с профилями, по полу)
2. WHEN администратор просматривает галерею пользователей, THE Bot System SHALL показать фото, имя, пол, краткое саммари и количество потоков
3. WHEN администратор ищет пользователя, THE Bot System SHALL искать по ID, username, имени, фамилии и потокам
4. WHEN администратор просматривает детали пользователя, THE Bot System SHALL показать полный профиль с историей активности
5. WHEN дашборд обновляется, THE Bot System SHALL автоматически подгружать новые данные через API без перезагрузки страницы
