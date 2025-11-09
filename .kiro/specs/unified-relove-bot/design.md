# Design Document

## Overview

Данный документ описывает объединённую архитектуру reLove Communication Bot, включающую базовую инфраструктуру (сессии, профили, путь героя) и проактивный интерфейс в стиле relove.ru. Система построена на принципах модульности, расширяемости и отказоустойчивости.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot API                          │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Proactive Bot Interface Layer                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Message      │  │ Trigger      │  │ UI/UX        │      │
│  │ Orchestrator │  │ Engine       │  │ Manager      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  Core Services Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Session      │  │ Journey      │  │ Natasha      │      │
│  │ Service      │  │ Service      │  │ Service      │      │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤      │
│  │ Profile      │  │ Broadcast    │  │ Analytics    │      │
│  │ Service      │  │ Service      │  │ Service      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    Data Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ PostgreSQL   │  │ Redis        │  │ Celery       │      │
│  │ Database     │  │ Cache        │  │ Tasks        │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Session Service
- Управление UserSession в БД
- Сохранение conversation_history
- Восстановление сессий после перезапуска
- Обновление User модели при завершении

### 2. Message Orchestrator
- Координация всех сообщений бота
- Определение текущего этапа пути
- Генерация stage-aware ответов
- Форматирование с UI элементами

### 3. Trigger Engine
- Отслеживание событий (неактивность, этапы, паттерны)
- Планирование проактивных сообщений
- Rate limiting (2 msg/day)
- Временные окна (8:00-22:00)

### 4. Journey Service
- Анализ текущего этапа пути героя через LLM
- Обновление JourneyProgress
- Адаптация стиля под этап
- Расчёт прогресса

### 5. Profile Service
- Автоматическая ротация профилей (каждые 24ч)
- Обновление через LLM с учётом UserActivityLog
- Персонализация рекомендаций потоков
- Трекинг взаимодействий

### 6. UI Manager
- Создание inline keyboards в стиле relove.ru
- Генерация quick replies под этап
- Форматирование progress indicators
- Применение минималистичного стиля

## Data Models

См. детальное описание в `.kiro/specs/proactive-bot-interface/design.md`

Основные модели:
- UserSession (сессии с conversation_history)
- ProactiveTrigger (запланированные проактивные сообщения)
- UserInteraction (трекинг взаимодействий)
- ProactivityConfig (конфигурация проактивности)
- JourneyProgress (прогресс по этапам пути)

## Integration Points

1. **Telegram Bot API** — получение/отправка сообщений
2. **LLM API (OpenAI/Anthropic)** — генерация ответов и анализ
3. **PostgreSQL** — хранение пользователей, сессий, логов
4. **Redis** — кэширование сессий и rate limiting
5. **Celery** — фоновые задачи (ротация, триггеры, архивация)

## Error Handling Strategy

1. **LLM Errors** — retry с exponential backoff, fallback на шаблоны
2. **Database Errors** — retry, queue для отложенной обработки
3. **Trigger Errors** — reschedule с задержкой, логирование
4. **Session Errors** — сохранение прогресса, уведомление пользователя

## Performance Considerations

1. **Caching** — Redis для сессий (TTL 1h), профилей (TTL 1h)
2. **Batching** — обработка пользователей пачками по 10
3. **Rate Limiting** — 30 msg/sec для рассылок, 2 proactive msg/day
4. **Indexing** — индексы на user_id, timestamp, journey_stage

## Security

1. **Data Encryption** — шифрование sensitive данных at rest
2. **Access Control** — admin-only endpoints с JWT auth
3. **Rate Limiting** — защита от спама и злоупотреблений
4. **Data Retention** — архивация логов старше 90 дней

## Deployment

1. **Environment** — Docker containers
2. **Database** — PostgreSQL 14+
3. **Cache** — Redis 7+
4. **Task Queue** — Celery с Redis broker
5. **Web Server** — Uvicorn (FastAPI)

Детальная информация о компонентах, паттернах проектирования и API endpoints доступна в `.kiro/specs/proactive-bot-interface/design.md`.
