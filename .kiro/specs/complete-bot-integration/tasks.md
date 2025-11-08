# Implementation Plan

## Overview
Этот план описывает пошаговую реализацию завершения разработки reLove Communication Bot с интеграцией профилей, пути героя и провокативного стиля Наташи.

---

## Phase 1: Core Infrastructure & Session Persistence

- [x] 1. Настройка middleware для проверки сессий и обновления профилей


  - Создать SessionCheckMiddleware для проверки активных сессий перед обработкой команд
  - Создать ProfileUpdateMiddleware для обновления last_seen_date и сохранения в UserActivityLog
  - Зарегистрировать middleware в bot.py
  - _Requirements: 1.1, 1.2, 4.1, 10.1, 10.2_



- [x] 1.1 Реализовать SessionCheckMiddleware

  - Написать класс SessionCheckMiddleware наследующий BaseMiddleware
  - Реализовать метод __call__ для проверки активных сессий
  - Добавить логику предложения завершения текущей сессии
  - Передавать active_session в data для handlers


  - _Requirements: 4.1, 4.2_


- [ ] 1.2 Реализовать ProfileUpdateMiddleware
  - Написать класс ProfileUpdateMiddleware наследующий BaseMiddleware
  - Реализовать обновление last_seen_date для каждого сообщения


  - Реализовать сохранение в UserActivityLog с типом 'message'
  - Добавить проверку возраста профиля (>7 дней)
  - Запускать фоновое обновление профиля если нужно
  - _Requirements: 10.1, 10.2, 10.3, 10.4_



- [ ] 2. Реализовать SessionPersistenceService
  - Создать класс SessionPersistenceService в relove_bot/services/session_service.py


  - Реализовать create_session() для создания UserSession в БД
  - Реализовать update_session() для обновления conversation_history
  - Реализовать complete_session() для завершения сессии и обновления User модели
  - Реализовать restore_active_sessions() для восстановления при перезапуске
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_




- [ ] 2.1 Создать методы управления сессиями
  - Написать create_session() с параметрами user_id, session_type
  - Написать get_active_session() для получения активной сессии пользователя

  - Написать update_session() для добавления сообщений в conversation_history
  - Написать complete_session() для закрытия сессии
  - _Requirements: 1.1, 1.2, 1.3, 1.5_



- [ ] 2.2 Реализовать восстановление сессий
  - Написать restore_active_sessions() для загрузки активных сессий из БД
  - Вызывать при старте бота в bot.py
  - Сохранять сессии в глобальный словарь active_sessions

  - _Requirements: 1.4_


- [ ] 2.3 Интегрировать с User моделью
  - Написать update_user_from_session() для обновления metaphysical_profile
  - Обновлять last_journey_stage из session_data
  - Вызывать при завершении сессии
  - _Requirements: 1.5, 2.3, 2.4_

- [x] 3. Обновить провокативную сессию для использования SessionPersistenceService

  - Изменить provocative_natasha.py для создания UserSession при /natasha
  - Обновлять UserSession при каждом сообщении пользователя
  - Завершать UserSession при /end_session
  - Удалить in-memory хранение active_sessions
  - _Requirements: 1.1, 1.2, 1.3, 1.5, 2.1, 2.2_

- [x] 3.1 Обновить обработчик /natasha

  - Использовать SessionPersistenceService.create_session()
  - Сохранять session_id в FSM state

  - Загружать существующую сессию если is_active=True
  - _Requirements: 1.1, 4.1_


- [ ] 3.2 Обновить обработчик сообщений в сессии
  - Использовать SessionPersistenceService.update_session()

  - Передавать conversation_history в LLM
  - Обновлять identified_patterns и core_issue
  - _Requirements: 1.2, 1.3, 2.1_


- [ ] 3.3 Обновить обработчик /end_session
  - Использовать SessionPersistenceService.complete_session()

  - Обновлять User.metaphysical_profile
  - Обновлять User.last_journey_stage

  - Показывать итоговую сводку
  - _Requirements: 1.5, 2.3, 2.4_

- [-] 4. Обновить гибкую диагностику для использования SessionPersistenceService


  - Изменить flexible_diagnostic.py для создания UserSession при /diagnostic
  - Обновлять UserSession при каждом сообщении
  - Завершать UserSession при завершении диагностики
  - _Requirements: 1.1, 1.2, 1.3, 1.5_


---

## Phase 2: Profile Rotation & Actualization

- [ ] 5. Создать ProfileRotationService
  - Создать класс ProfileRotationService в relove_bot/services/profile_rotation_service.py
  - Реализовать rotate_profiles() для фоновой ротации
  - Реализовать get_users_for_rotation() для получения пользователей
  - Реализовать update_user_profile() для обновления профиля
  - _Requirements: 10.4, 10.5, 10.6, 10.7, 11.1, 11.2, 11.3_

- [ ] 5.1 Реализовать получение пользователей для ротации
  - Написать get_users_for_rotation() с фильтрами
  - Фильтр: last_seen_date в последние 30 дней
  - Фильтр: markers['profile_updated_at'] старше 7 дней или отсутствует
  - Сортировка по last_seen_date DESC
  - _Requirements: 11.1, 11.2_

- [ ] 5.2 Реализовать обновление профиля пользователя
  - Написать update_user_profile() с параметром user
  - Получить последние 50 записей из UserActivityLog
  - Получить посты пользователя из Telegram через telegram_service
  - Сформировать промпт для LLM с учётом старого psychological_summary
  - Отправить в LLM для обновлённого анализа
  - Обновить psychological_summary, streams, markers['profile_updated_at']
  - _Requirements: 10.4, 10.5, 10.6, 10.7, 11.3, 11.4_

- [ ] 5.3 Реализовать пакетную обработку
  - Написать process_batch() для обработки пачки пользователей
  - Обрабатывать по 10 пользователей за раз
  - Добавить паузу 5 секунд между пачками
  - Логировать ошибки без остановки процесса
  - _Requirements: 11.4_

- [ ] 5.4 Реализовать логирование статистики
  - Написать log_rotation_stats() для записи результатов
  - Считать: обработано, обновлено, ошибок, пропущено
  - Записывать в лог с уровнем INFO
  - _Requirements: 11.8_

- [ ] 6. Создать фоновую задачу ротации профилей
  - Создать profile_rotation_task() в relove_bot/tasks/background_tasks.py
  - Запускать ProfileRotationService.rotate_profiles() каждые 24 часа
  - Обрабатывать ошибки без остановки задачи
  - Логировать начало и конец ротации
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

- [ ] 6.1 Реализовать запуск фоновой задачи
  - Добавить запуск profile_rotation_task() в bot.py при старте
  - Использовать asyncio.create_task()
  - Добавить graceful shutdown при остановке бота
  - _Requirements: 11.1_

- [ ] 7. Обновить скрипт fill_profiles.py для массового обновления
  - Использовать ProfileRotationService вместо старой логики
  - Добавить параметры командной строки (--all, --user-id, --batch-size)
  - Показывать прогресс-бар через tqdm
  - Выводить итоговую статистику
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 8. Создать миграцию для UserActivityLogArchive
  - Создать alembic миграцию для таблицы user_activity_logs_archive
  - Добавить индексы на user_id, timestamp, archived_at
  - _Requirements: 10.10_

- [ ] 9. Создать фоновую задачу архивации логов
  - Создать log_archive_task() в relove_bot/tasks/background_tasks.py
  - Архивировать логи старше 90 дней
  - Архивировать если у пользователя >1000 логов
  - Запускать каждые 7 дней
  - _Requirements: 10.10_

---

## Phase 3: Journey Integration & Tracking

- [ ] 10. Создать JourneyTrackingService
  - Создать класс JourneyTrackingService в relove_bot/services/journey_service.py
  - Реализовать analyze_journey_stage() для определения этапа
  - Реализовать update_journey_stage() для обновления этапа
  - Реализовать get_journey_progress() для получения прогресса
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 10.8, 10.9_

- [ ] 10.1 Реализовать анализ этапа пути героя
  - Написать analyze_journey_stage() с параметрами user_id, conversation_history
  - Получить текущий last_journey_stage из User
  - Сформировать промпт для LLM с описанием этапов из hero_journey.py
  - Отправить в LLM для определения нового этапа
  - Вернуть JourneyStageEnum или None
  - _Requirements: 9.1, 9.2, 10.8_

- [ ] 10.2 Реализовать обновление этапа
  - Написать update_journey_stage() с параметрами user_id, new_stage
  - Обновить User.last_journey_stage
  - Создать запись в JourneyProgress с новым этапом
  - Добавить старый этап в completed_stages
  - Записать stage_start_time
  - _Requirements: 9.3, 10.9_

- [ ] 10.3 Реализовать получение прогресса
  - Написать get_journey_progress() с параметром user_id
  - Получить все записи JourneyProgress для пользователя
  - Вернуть список этапов с временем начала
  - _Requirements: 9.4_

- [ ] 11. Интегрировать JourneyTrackingService с провокативной сессией
  - Обновить provocative_natasha.py для использования JourneyTrackingService
  - Передавать текущий last_journey_stage в промпт LLM
  - Анализировать этап после каждых 5 сообщений
  - Обновлять этап при завершении сессии
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ] 11.1 Обновить промпт для учёта этапа
  - Добавить в NATASHA_PROVOCATIVE_PROMPT информацию о текущем этапе
  - Передавать описание этапа из JOURNEY_STAGES
  - Адаптировать провокации под этап
  - _Requirements: 9.2_

- [ ] 11.2 Добавить анализ этапа в сессию
  - Вызывать JourneyTrackingService.analyze_journey_stage() после каждых 5 сообщений
  - Сохранять новый этап в session_data
  - Обновлять User.last_journey_stage при изменении
  - _Requirements: 9.1, 9.3, 10.8_

- [ ] 11.3 Обновить завершение сессии
  - Вызывать JourneyTrackingService.update_journey_stage() при /end_session
  - Показывать прогресс по этапам в итоговой сводке
  - _Requirements: 9.4, 10.9_

- [ ] 12. Создать команду /my_journey для визуализации пути
  - Создать обработчик для /my_journey
  - Получить JourneyProgress для пользователя
  - Показать текущий этап и пройденные этапы
  - Показать время на каждом этапе
  - _Requirements: 9.5_

---

## Phase 4: Admin Broadcast & Dashboard

- [ ] 13. Создать AdminBroadcastService
  - Создать класс AdminBroadcastService в relove_bot/services/admin_broadcast_service.py
  - Реализовать broadcast_message() для отправки рассылки
  - Реализовать get_users_by_criteria() для фильтрации пользователей
  - Реализовать parse_criteria() для парсинга критериев
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 13.1 Реализовать парсинг критериев
  - Написать parse_criteria() для преобразования строки в Dict
  - Поддержать фильтры: gender, journey_stage, streams, markers
  - Пример: "gender=female,journey_stage=CALL_TO_ADVENTURE,streams=Путь Героя"
  - _Requirements: 3.1_

- [ ] 13.2 Реализовать фильтрацию пользователей
  - Написать get_users_by_criteria() с SQLAlchemy фильтрами
  - Фильтр по gender через User.gender
  - Фильтр по journey_stage через User.last_journey_stage
  - Фильтр по streams через User.streams.contains()
  - Фильтр по markers через User.markers[key].astext
  - _Requirements: 3.2_

- [ ] 13.3 Реализовать рассылку с rate limiting
  - Написать broadcast_message() с параметрами message, criteria
  - Создать RateLimiter для 30 msg/sec
  - Отправлять сообщения через bot.send_message()
  - Обрабатывать BotBlocked и помечать пользователя is_active=False
  - Считать статистику: sent, errors, blocked
  - _Requirements: 3.3, 3.4, 3.5_

- [ ] 14. Обновить обработчик /broadcast в admin.py
  - Использовать AdminBroadcastService вместо старой логики
  - Добавить UI для ввода критериев
  - Показывать предпросмотр количества пользователей
  - Показывать статистику после рассылки
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 15. Создать AnalyzeReadinessService
  - Создать класс AnalyzeReadinessService в relove_bot/services/readiness_service.py
  - Реализовать analyze_readiness() для анализа готовности к потокам
  - Использовать UserActivityLog и psychological_summary
  - Возвращать оценку готовности для каждого потока (0-100%)
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 15.1 Реализовать анализ готовности
  - Написать analyze_readiness() с параметром user_id
  - Получить последние 50 записей из UserActivityLog
  - Получить psychological_summary из User
  - Сформировать промпт для LLM с описанием потоков
  - Получить оценку готовности для каждого потока
  - Вернуть топ-3 рекомендованных потока
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 16. Обновить обработчик /analyze_readiness
  - Использовать AnalyzeReadinessService вместо TODO
  - Показывать топ-3 потока с обоснованием
  - Добавить кнопки для выбора потока
  - Сохранять выбор в markers['interested_stream']
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 17. Обновить веб-дашборд
  - Обновить dashboard() в web.py для показа актуальных данных
  - Добавить фильтры по journey_stage
  - Показывать markers['profile_updated_at'] для каждого пользователя
  - Добавить кнопку "Обновить профиль" для ручного обновления
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ] 17.1 Добавить фильтры в галерею пользователей
  - Обновить users_gallery_api() для поддержки фильтров
  - Добавить параметры: gender, journey_stage, streams
  - Обновить UI для выбора фильтров
  - _Requirements: 13.2, 13.3_

- [ ] 17.2 Добавить детали пользователя
  - Обновить user_details() для показа полного профиля
  - Показывать psychological_summary, metaphysical_profile
  - Показывать историю JourneyProgress
  - Показывать последние 20 записей UserActivityLog
  - _Requirements: 13.4_

- [ ] 17.3 Добавить автообновление дашборда
  - Обновить dashboard_data_api() для возврата актуальных данных
  - Добавить JavaScript для автообновления каждые 30 секунд
  - Обновлять без перезагрузки страницы
  - _Requirements: 13.5_

---

## Phase 5: Error Handling & Optimization

- [ ] 18. Реализовать retry логику для LLM
  - Создать LLMServiceWithRetry в relove_bot/services/llm_service.py
  - Реализовать analyze_with_retry() с max_retries=2
  - Добавить экспоненциальную задержку (2^attempt секунд)
  - Логировать все попытки и ошибки
  - _Requirements: 7.1, 7.2_

- [ ] 18.1 Обновить все вызовы LLM
  - Заменить llm_service.analyze() на llm_service.analyze_with_retry()
  - В ProfileRotationService
  - В SessionPersistenceService
  - В JourneyTrackingService
  - В AnalyzeReadinessService
  - _Requirements: 7.1_

- [ ] 19. Реализовать восстановление сессий после ошибок
  - Создать recover_session_on_error() в session_service.py
  - Сохранять last_error и error_timestamp в session_data
  - Уведомлять пользователя о сохранении прогресса
  - Позволять продолжить сессию после ошибки
  - _Requirements: 7.3, 7.4_

- [ ] 20. Добавить уведомления администраторам
  - Создать notify_admins() в relove_bot/utils/notifications.py
  - Отправлять уведомления при критических ошибках
  - Отправлять при недоступности LLM >5 минут
  - Отправлять при ошибках фоновых задач
  - _Requirements: 7.5_

- [ ] 21. Добавить индексы в БД
  - Создать миграцию для добавления индексов
  - Индекс на User.last_seen_date
  - Индекс на User.last_journey_stage
  - Индекс на UserActivityLog.timestamp
  - Индекс на UserSession.is_active
  - _Requirements: Performance optimization_

- [ ] 22. Реализовать кэширование
  - Добавить кэширование активных сессий в памяти
  - Кэшировать профили пользователей на 1 час
  - Кэшировать результаты LLM по хэшу промпта
  - Использовать Redis или in-memory dict
  - _Requirements: Performance optimization_

---

## Phase 6: Testing & Documentation

- [ ]* 23. Написать unit тесты
  - Тесты для ProfileRotationService.update_user_profile()
  - Тесты для SessionPersistenceService.create_session()
  - Тесты для JourneyTrackingService.analyze_journey_stage()
  - Тесты для AdminBroadcastService.get_users_by_criteria()
  - _Requirements: Testing_

- [ ]* 24. Написать integration тесты
  - Тест полного цикла ротации профиля
  - Тест создания и восстановления сессии
  - Тест обновления этапа пути героя
  - Тест рассылки с фильтрацией
  - _Requirements: Testing_

- [ ]* 25. Обновить документацию
  - Обновить README.md с новыми командами
  - Обновить ARCHITECTURE.md с новыми компонентами
  - Обновить PROJECT_STATUS.md с завершёнными задачами
  - Создать DEPLOYMENT.md с инструкциями по развёртыванию
  - _Requirements: Documentation_

---

## Phase 7: Cleanup & Refactoring

- [ ] 26. Удалить старый diagnostic.py
  - Удалить файл relove_bot/handlers/diagnostic.py
  - Удалить регистрацию команды /start_diagnostic
  - Обновить импорты в других файлах
  - Обновить документацию
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 27. Обновить конверсионные флаги
  - Обновить обработчики для установки has_started_journey
  - Обновить обработчики для установки has_completed_journey
  - Добавить трекинг переходов на платформу (has_visited_platform)
  - Создать команду /stats для администраторов
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 28. Финальное тестирование
  - Протестировать все сценарии end-to-end
  - Проверить работу фоновых задач
  - Проверить работу дашборда
  - Проверить работу рассылки
  - Проверить восстановление после перезапуска
  - _Requirements: All_
