# Логика обогащения профилей из нескольких каналов

## Проблема

Раньше: если пользователь был в 3 каналах, его профиль заполнялся только данными из первого канала. Посты из остальных каналов игнорировались.

## Решение

Новая двухэтапная логика:

### Этап 1: Сбор данных из ВСЕХ каналов

```python
for channel in all_relove_channels:
    # Получаем участников канала
    participants = get_participants(channel)
    
    # Получаем посты из канала
    messages = get_messages(channel, limit=1000)
    
    # Накапливаем данные по каждому пользователю
    for user in participants:
        user_data_accumulator[user.id] = {
            'tg_user': user,
            'channels': [channel1, channel2, ...],  # Все каналы где найден
            'posts': [msg1, msg2, ...]  # ВСЕ посты из ВСЕХ каналов
        }
```

### Этап 2: Обработка пользователей с полными данными

```python
for user_id, user_data in user_data_accumulator.items():
    # Сохраняем/обновляем в БД
    db_user = save_user_to_db(user_data['tg_user'])
    
    # Заполняем профиль ОДИН РАЗ с данными из ВСЕХ каналов
    if needs_profile_fill(db_user):
        fill_profile_with_posts(
            user=db_user,
            posts=user_data['posts'],  # Посты из ВСЕХ каналов
            channels=user_data['channels']
        )
```

## Структура данных

### user_data_accumulator

```python
{
    511588742: {  # user_id
        'tg_user': <TelethonUser>,
        'channels': [
            'Прошлые Жизни reLove',
            'reLove open Chat',
            'ЧАТ RELOVE'
        ],
        'posts': [
            <Message 1 from channel 1>,
            <Message 2 from channel 1>,
            <Message 3 from channel 2>,
            <Message 4 from channel 3>,
            ...
        ]
    },
    ...
}
```

## Пример сценария

### Пользователь @Irinabalerina7 в 3 каналах:

**Канал 1: "Прошлые Жизни reLove"**
- Участник: ✅
- Посты: 15 сообщений
- Действие: Добавляем в accumulator

**Канал 2: "reLove open Chat"**
- Участник: ✅ (тот же user_id)
- Посты: 23 сообщения
- Действие: Добавляем посты к существующим в accumulator
- Статистика: `duplicates_found += 1`

**Канал 3: "ЧАТ RELOVE"**
- Участник: ✅ (тот же user_id)
- Посты: 8 сообщений
- Действие: Добавляем посты к существующим в accumulator
- Статистика: `duplicates_found += 1`

**Итоговая обработка:**
```python
user_data = {
    'tg_user': @Irinabalerina7,
    'channels': [
        'Прошлые Жизни reLove',
        'reLove open Chat',
        'ЧАТ RELOVE'
    ],
    'posts': [
        ... 15 постов из канала 1 ...
        ... 23 поста из канала 2 ...
        ... 8 постов из канала 3 ...
    ]  # Всего 46 постов
}

# Генерируем профиль ОДИН РАЗ на основе ВСЕХ 46 постов
psychological_summary = analyze_text(
    bio + "\n\n" + all_46_posts
)
```

## Преимущества

✅ **Полнота данных**: Профиль учитывает активность во ВСЕХ каналах  
✅ **Нет дублирования**: Каждый пользователь обрабатывается только 1 раз  
✅ **Эффективность**: Не тратим API-запросы на повторную обработку  
✅ **Качество анализа**: LLM видит полную картину активности пользователя  

## Статистика

После обработки:

```
Channels processed: 3
Users found: 150 (50 + 60 + 40)
Unique users: 80
Duplicates found: 70 (пересечения между каналами)
Profiles filled: 80 (каждый с данными из всех каналов)
```

## Код

**Основной метод**: `process_all_relove_channels()`

**Этап 1**: `collect_user_data_from_channel()` - собирает данные  
**Этап 2**: `process_accumulated_users()` - обрабатывает с полными данными  
**Заполнение**: `fill_user_profile_with_posts()` - генерирует профиль

## Использование

```bash
# Обработать все каналы reLove
python scripts/profiles/fill_profiles_from_channels.py --all

# С ограничением
python scripts/profiles/fill_profiles_from_channels.py --all --limit 100

# Конкретный канал
python scripts/profiles/fill_profiles_from_channels.py --channel @relove
```

## Важные детали

1. **Сортировка постов**: Посты сортируются по дате (новые первые)
2. **Лимит постов**: Берём последние 50 постов для анализа
3. **Формат**: `[YYYY-MM-DD] текст сообщения`
4. **Bio + Посты**: Анализируется `bio + все посты из всех каналов`
5. **Фото профиля**: Загружается один раз и передаётся в Vision API

## Обработка ошибок

- Если не удалось получить bio → используем только посты
- Если не удалось получить фото → анализируем только текст
- Если нет постов и bio → пропускаем пользователя
- Все ошибки логируются, но не останавливают обработку

## Производительность

- **Сбор данных**: ~2-5 сек на канал (зависит от размера)
- **Обработка пользователя**: ~20-30 сек (LLM анализ)
- **Общее время**: Зависит от количества каналов и пользователей

Для 3 каналов с 80 уникальными пользователями: ~40-50 минут
