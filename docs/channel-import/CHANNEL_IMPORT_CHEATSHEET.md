# 🚀 Шпаргалка: Импорт из каналов reLove

## Первый запуск (один раз)

```bash
# Авторизация в Telegram
python scripts/test_telethon_connection.py
# Введите номер телефона и код из Telegram
```

## Быстрые команды

```bash
# Посмотреть доступные каналы
python scripts/quick_channel_list.py

# Импорт из всех каналов (быстро, без профилей)
python scripts/fill_profiles_from_channels.py --all --no-fill

# Импорт из всех каналов (с профилями)
python scripts/fill_profiles_from_channels.py --all

# Импорт из конкретного канала
python scripts/fill_profiles_from_channels.py --channel @reloveinfo

# Импорт с ограничением
python scripts/fill_profiles_from_channels.py --all --limit 100

# Заполнить профили после импорта
python scripts/fill_profiles.py --all --batch-size 20
```

## Рекомендуемый workflow

```bash
# 1. Проверка каналов
python scripts/quick_channel_list.py

# 2. Быстрый импорт пользователей
python scripts/fill_profiles_from_channels.py --all --no-fill

# 3. Заполнение профилей пакетами
python scripts/fill_profiles.py --all --batch-size 20
```

## Проверка результатов

```bash
# В боте (для админов)
/admin_find_users limit=10
/admin_user_info user_id=123456

# В базе данных
SELECT COUNT(*) FROM users WHERE is_active = true;
```

## Частые ошибки

| Ошибка | Решение |
|--------|---------|
| "Not authorized" | `python scripts/test_telethon_connection.py` |
| "Could not find entity" | Проверьте username или вступите в канал |
| "A wait of X seconds" | Подождите (rate limit) |
| "No channels found" | Вступите в каналы reLove |

## Важно помнить

- ⚠️ Broadcast каналы: нельзя получить подписчиков
- ✅ Группы/супергруппы: можно получить всех участников
- 🔐 Не делитесь файлом `.session`
- ⏱️ Rate limits: ~20 запросов/сек

## Логи

```bash
# Просмотр логов
cat logs/fill_profiles_from_channels.log

# Последние 50 строк
tail -n 50 logs/fill_profiles_from_channels.log

# Windows
type logs\fill_profiles_from_channels.log
```

## Автоматизация

```bash
# Cron (Linux/Mac) - каждый день в 3:00
0 3 * * * cd /path/to/project && python scripts/fill_profiles_from_channels.py --all --no-fill
```

---

📚 **Полная документация:** `CHANNEL_IMPORT_GUIDE.md`
