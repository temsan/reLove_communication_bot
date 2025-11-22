# Архитектура reLove Communication Bot

## 1. Модель пользователя (User)

Минималистичная, гибкая и масштабируемая:
- **id**: Telegram user_id
- **username, first_name, last_name**: идентификация
- **is_active**: активен ли пользователь
- **gender**: пол ('male', 'female', 'unknown')
- **context**: JSON — персональный контекст (summary, relove_context, любые временные данные)
- **markers**: JSON — любые пользовательские свойства (гибкие маркеры, например, city, VIP, interests, tags, source и др.)

## 2. Пример работы с markers/context

```python
# Установка маркера
user.markers = user.markers or {}
user.markers['city'] = 'Москва'
user.markers['VIP'] = True

# Добавление признака в context
user.context = user.context or {}
user.context['relove_context'] = '...'
user.context['last_message'] = '...'
```

## 3. Пример фильтрации пользователей

```python
# Найти всех VIP-пользователей из Москвы
query = session.query(User).filter(
    User.is_active == True,
    User.markers['city'].astext == 'Москва',
    User.markers['VIP'].astext == 'true'
)
```

## 4. Пример обновления данных при касании

```python
async def update_user_on_touch(user_id, message, session):
    user = await session.get(User, user_id)
    if not user:
        user = User(id=user_id, ...)
        session.add(user)
    user.context = user.context or {}
    user.context['last_message'] = message.text
    # ... любые другие обновления
    await session.commit()
```

## 5. Масштабируемость и интеграции
- markers/context позволяют добавлять любые свойства без миграций
- легко интегрировать внешние сервисы (CRM, рассылки, ML)
- можно добавить историю действий, если потребуется (отдельная таблица или внешний сервис)

## 6. Примеры сценариев
- Сегментация для рассылок: по любым признакам из markers/context
- Персонализация: рекомендации и summary в context
- Аналитика: подсчёт пользователей по любым маркерам

---

## Итог
Вся логика — вокруг одной гибкой модели User. Любые новые сценарии реализуются без изменений схемы БД. Это современно, быстро и удобно для роста.
