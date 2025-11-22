# Заполнение профилей из каналов Telegram

Скрипт `fill_profiles_from_channels.py` использует Telethon user-клиент для получения участников из каналов и чатов reLove и автоматического заполнения их профилей.

## Преимущества user-клиента

- ✅ Доступ к участникам каналов (у ботов нет такого доступа)
- ✅ Получение данных из групп и супергрупп
- ✅ Автоматический поиск всех каналов reLove
- ✅ Массовое заполнение профилей

## Требования

1. **Telethon** должен быть установлен:
```bash
pip install telethon
```

2. **Настройки в .env**:
```env
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
TG_SESSION=relove_bot
```

3. **Первый запуск** - нужно авторизоваться:
   - Скрипт попросит номер телефона
   - Затем код из Telegram
   - Сессия сохранится в файл `relove_bot.session`

## Использование

### 1. Показать все каналы reLove

```bash
python scripts/fill_profiles_from_channels.py --list-channels
```

Найдет все каналы и чаты с "relove" в названии.

### 2. Обработать все каналы reLove

```bash
python scripts/fill_profiles_from_channels.py --all
```

Найдет все каналы reLove, получит участников и заполнит их профили.

### 3. Обработать конкретный канал

```bash
python scripts/fill_profiles_from_channels.py --channel @reloveinfo
```

Или по ID:
```bash
python scripts/fill_profiles_from_channels.py --channel -1001234567890
```

### 4. Ограничить количество участников

```bash
python scripts/fill_profiles_from_channels.py --all --limit 100
```

Обработает только первых 100 участников из каждого канала.

### 5. Только импорт без заполнения профилей

```bash
python scripts/fill_profiles_from_channels.py --all --no-fill
```

Только добавит пользователей в БД, без анализа профилей (быстрее).

## Примеры

### Полный цикл для всех каналов

```bash
# 1. Сначала посмотрим какие каналы найдены
python scripts/fill_profiles_from_channels.py --list-channels

# 2. Импортируем пользователей без заполнения профилей (быстро)
python scripts/fill_profiles_from_channels.py --all --no-fill

# 3. Потом заполним профили через обычный скрипт
python scripts/fill_profiles.py --all --batch-size 20
```

### Обработка конкретного канала с лимитом

```bash
python scripts/fill_profiles_from_channels.py --channel @reloveinfo --limit 50
```

### Массовая обработка всех каналов

```bash
python scripts/fill_profiles_from_channels.py --all
```

## Что делает скрипт

1. **Поиск каналов** - находит все каналы/чаты с "relove" в названии
2. **Получение участников** - через Telethon API получает список участников
3. **Сохранение в БД** - добавляет/обновляет пользователей в базе
4. **Заполнение профилей** - через ProfileService анализирует каждого пользователя
5. **Статистика** - выводит результаты обработки

## Логи

Логи сохраняются в:
- `logs/fill_profiles_from_channels.log` - детальный лог
- Консоль - основные события с прогресс-баром

## Ограничения

### Broadcast каналы
Для публичных broadcast каналов (где админ просто публикует посты) нельзя получить список подписчиков через API. Можно получить только:
- Админов канала
- Пользователей, которые писали в комментариях (если включены)

### Приватные каналы
Нужно быть участником канала, чтобы получить список участников.

### Rate limits
Telegram ограничивает количество запросов. Скрипт делает паузы между запросами, но при большом количестве пользователей может потребоваться время.

## Troubleshooting

### "Could not find the input entity"
Канал не найден. Проверьте:
- Username канала правильный
- Вы являетесь участником канала
- Канал существует

### "A wait of X seconds is required"
Telegram rate limit. Подождите указанное время.

### "The channel specified is private and you lack permission to access it"
Нужно вступить в канал сначала.

## Безопасность

⚠️ **Важно:**
- Не делитесь файлом `.session` - это ваш доступ к аккаунту
- Используйте отдельный аккаунт для автоматизации
- Соблюдайте Terms of Service Telegram
- Не спамьте пользователей

## Интеграция с ботом

После импорта пользователей они будут доступны в боте:
- Админ-команды `/admin_find_users`, `/admin_user_info`
- Автоматическое обновление профилей через фоновые задачи
- Поиск похожих пользователей через `/similar`
