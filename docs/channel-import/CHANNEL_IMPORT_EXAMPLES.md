# 💡 Примеры использования импорта из каналов

## 🎯 Сценарий 1: Первый запуск проекта

**Задача:** Импортировать всех пользователей из каналов reLove в новую БД.

### Шаги:

```bash
# 1. Авторизация (один раз)
python scripts/test_telethon_connection.py
# Введите: +79991234567
# Введите код из Telegram: 12345

# 2. Проверка доступных каналов
python scripts/quick_channel_list.py

# Вывод:
# ✅ Found 3 reLove channels/groups:
# 1. 📢 Channel reLove Community
#    Username: @reloveinfo
#    ID: -1001234567890
# 2. 👥 Group reLove Chat
#    Username: @relovechat
#    ID: -1009876543210
# 3. 👥 Group Путь Героя reLove
#    Username: no username
#    ID: -1005555555555

# 3. Быстрый импорт всех пользователей
python scripts/fill_profiles_from_channels.py --all --no-fill

# Вывод:
# Processing: reLove Community
# Found 1250 participants
# Processing reLove Community: 100%|████| 1250/1250 [02:05<00:00]
# 
# Processing: reLove Chat
# Found 850 participants
# Processing reLove Chat: 100%|████| 850/850 [01:25<00:00]
# 
# STATISTICS
# Channels processed: 3
# Users found: 2500
# Users added: 2300
# Users updated: 200
# Profiles filled: 0
# Errors: 0

# 4. Заполнение профилей пакетами
python scripts/fill_profiles.py --all --batch-size 20

# Вывод:
# Updating profiles: 100%|████| 2500/2500 [25:00<00:00]
# Update completed: processed=2500, updated=2500, errors=0
```

**Результат:** 2500 пользователей в БД с заполненными профилями.

---

## 🔄 Сценарий 2: Регулярное обновление

**Задача:** Еженедельно обновлять список пользователей и их профили.

### Скрипт для cron:

```bash
#!/bin/bash
# update_relove_users.sh

cd /path/to/project

# Активируем виртуальное окружение
source venv/bin/activate

# Обновляем пользователей из каналов
python scripts/fill_profiles_from_channels.py --all --no-fill

# Обновляем профили активных пользователей
python scripts/fill_profiles.py --all --batch-size 50

# Отправляем уведомление
echo "reLove users updated: $(date)" >> logs/cron.log
```

### Настройка cron:

```bash
# Каждое воскресенье в 3:00
0 3 * * 0 /path/to/update_relove_users.sh
```

---

## 🎯 Сценарий 3: Импорт из конкретного канала

**Задача:** Добавить пользователей только из нового канала "Женский поток".

```bash
# Импорт из конкретного канала
python scripts/fill_profiles_from_channels.py --channel @relove_women --limit 500

# Вывод:
# Processing: Женский поток reLove
# Found 450 participants
# Processing: 100%|████| 450/450 [05:30<00:00]
# 
# STATISTICS
# Channels processed: 1
# Users found: 450
# Users added: 380
# Users updated: 70
# Profiles filled: 450
# Errors: 0
```

**Результат:** 450 пользователей из канала "Женский поток" добавлены с профилями.

---

## 🧪 Сценарий 4: Тестирование на малой выборке

**Задача:** Протестировать импорт на 10 пользователях перед полным запуском.

```bash
# Тест на 10 пользователях
python scripts/fill_profiles_from_channels.py --channel @reloveinfo --limit 10

# Вывод:
# Processing: reLove Community
# Found 10 participants
# Processing: 100%|████| 10/10 [00:15<00:00]
# 
# STATISTICS
# Channels processed: 1
# Users found: 10
# Users added: 8
# Users updated: 2
# Profiles filled: 10
# Errors: 0

# Проверка результатов в БД
python -c "
from relove_bot.db.session import async_session
from relove_bot.db.models import User
from sqlalchemy import select
import asyncio

async def check():
    async with async_session() as session:
        result = await session.execute(
            select(User).limit(10)
        )
        users = result.scalars().all()
        for user in users:
            print(f'{user.id} | @{user.username} | {user.first_name}')

asyncio.run(check())
"
```

**Результат:** 10 пользователей импортированы, можно проверить качество.

---

## 📊 Сценарий 5: Аналитика после импорта

**Задача:** Получить статистику по импортированным пользователям.

```bash
# Импорт
python scripts/fill_profiles_from_channels.py --all

# Статистика по полу
python scripts/gender_stats.py

# Вывод:
# Gender Statistics:
# Female: 1500 (60%)
# Male: 800 (32%)
# Unknown: 200 (8%)
# Total: 2500

# Поиск пользователей через бота (для админов)
# В Telegram:
/admin_find_users gender=female limit=20

# Вывод:
# id | username | gender | summary
# 123456 | @user1 | female | Интересуется психологией...
# 234567 | @user2 | female | Проходит путь героя...
# ...
```

---

## 🎯 Сценарий 6: Импорт с фильтрацией

**Задача:** Импортировать только активных пользователей из последних сообщений.

```python
# custom_import.py
import asyncio
from scripts.fill_profiles_from_channels import ChannelProfileFiller

async def import_active_users():
    filler = ChannelProfileFiller()
    
    await filler.client.start()
    
    # Получаем участников
    participants = await filler.get_channel_participants('@reloveinfo')
    
    # Фильтруем активных (например, по last_seen)
    active_users = [
        user for user in participants
        if hasattr(user.status, 'was_online') and 
           user.status.was_online is not None
    ]
    
    print(f"Active users: {len(active_users)} / {len(participants)}")
    
    # Импортируем только активных
    async with async_session() as session:
        for user in active_users:
            await filler.save_user_to_db(user, session)
            await filler.fill_user_profile(user, session)
    
    await filler.client.disconnect()

asyncio.run(import_active_users())
```

---

## 🔍 Сценарий 7: Поиск похожих пользователей

**Задача:** После импорта найти пользователей с похожими интересами.

```bash
# 1. Импорт с заполнением профилей
python scripts/fill_profiles_from_channels.py --all

# 2. В боте (для любого пользователя)
# Telegram:
/similar 10

# Вывод:
# Похожие пользователи:
# ID: 123456 | username: @user1 | контекст: Интересуется психологией...
# ID: 234567 | username: @user2 | контекст: Проходит путь героя...
# ...

# 3. Программно
python -c "
from relove_bot.rag.pipeline import get_profile_summary
from relove_bot.db.vector import search_similar_users
from relove_bot.db.session import async_session
import asyncio

async def find_similar(user_id):
    async with async_session() as session:
        profile = await get_profile_summary(user_id, session)
        if profile:
            from relove_bot.rag.embeddings import get_text_embedding
            embedding = await get_text_embedding(profile)
            hits = search_similar_users(embedding, top_k=5)
            for hit in hits:
                print(f'{hit.id} | {hit.payload.get(\"username\")}')

asyncio.run(find_similar(123456))
"
```

---

## 📧 Сценарий 8: Таргетированная рассылка

**Задача:** Отправить сообщение пользователям с определенным профилем.

```python
# targeted_broadcast.py
import asyncio
from relove_bot.db.session import async_session
from relove_bot.db.models import User
from relove_bot.bot import bot
from sqlalchemy import select

async def send_to_women_interested_in_hero_journey():
    """Рассылка женщинам, интересующимся путем героя"""
    
    async with async_session() as session:
        # Находим пользователей
        result = await session.execute(
            select(User).where(
                User.is_active == True,
                User.gender == 'female',
                User.markers['summary'].astext.contains('путь героя')
            )
        )
        users = result.scalars().all()
        
        print(f"Found {len(users)} users")
        
        # Отправляем сообщение
        message = (
            "🔥 Привет! Мы заметили, что тебя интересует Путь Героя.\n\n"
            "Скоро стартует новый женский поток. Хочешь узнать подробности?"
        )
        
        for user in users:
            try:
                await bot.send_message(user.id, message)
                print(f"✅ Sent to {user.id} (@{user.username})")
                await asyncio.sleep(1)  # Rate limit
            except Exception as e:
                print(f"❌ Error sending to {user.id}: {e}")

asyncio.run(send_to_women_interested_in_hero_journey())
```

---

## 🎯 Сценарий 9: Миграция из старой БД

**Задача:** Дополнить существующую БД пользователями из каналов.

```bash
# 1. Бэкап текущей БД
pg_dump relove_bot > backup_before_import.sql

# 2. Импорт новых пользователей (не затрет существующих)
python scripts/fill_profiles_from_channels.py --all --no-fill

# Вывод:
# STATISTICS
# Users found: 3000
# Users added: 500      # Только новые
# Users updated: 2500   # Обновлены существующие
# Errors: 0

# 3. Заполнение профилей только для новых
python -c "
from relove_bot.db.session import async_session
from relove_bot.db.models import User
from relove_bot.services.profile_service import ProfileService
from sqlalchemy import select
import asyncio

async def fill_new_users():
    async with async_session() as session:
        # Находим пользователей без профилей
        result = await session.execute(
            select(User).where(
                User.markers['summary'].astext == None
            )
        )
        users = result.scalars().all()
        
        print(f'Found {len(users)} users without profiles')
        
        profile_service = ProfileService(session)
        for user in users:
            await profile_service.analyze_profile(user.id, user)
            print(f'Filled profile for {user.id}')

asyncio.run(fill_new_users())
"
```

---

## 🔄 Сценарий 10: Автоматическое обновление через бота

**Задача:** Настроить автоматическое обновление профилей в фоне.

```python
# В relove_bot/tasks/background_tasks.py уже есть:

async def profile_rotation_task():
    """Фоновая задача для обновления профилей"""
    while True:
        try:
            # Каждые 24 часа обновляем профили
            await asyncio.sleep(24 * 60 * 60)
            
            # Импорт новых пользователей
            filler = ChannelProfileFiller()
            await filler.client.start()
            await filler.process_all_relove_channels(
                fill_profiles=False  # Быстрый импорт
            )
            await filler.client.disconnect()
            
            # Обновление профилей
            async with async_session() as session:
                service = ProfileRotationService(session)
                users = await service.get_users_for_rotation()
                for user in users:
                    await service.update_user_profile(user)
            
        except Exception as e:
            logger.error(f"Error in profile rotation: {e}")
```

**Запуск:** Автоматически при старте бота.

---

## 📊 Сценарий 11: Экспорт данных для анализа

**Задача:** Экспортировать импортированных пользователей в CSV для анализа.

```python
# export_users.py
import asyncio
import csv
from relove_bot.db.session import async_session
from relove_bot.db.models import User
from sqlalchemy import select

async def export_to_csv():
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        with open('relove_users.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ID', 'Username', 'First Name', 'Last Name', 
                'Gender', 'Is Active', 'Registration Date', 'Summary'
            ])
            
            for user in users:
                writer.writerow([
                    user.id,
                    user.username,
                    user.first_name,
                    user.last_name,
                    user.gender.value if user.gender else '',
                    user.is_active,
                    user.registration_date,
                    user.markers.get('summary', '') if user.markers else ''
                ])
        
        print(f"Exported {len(users)} users to relove_users.csv")

asyncio.run(export_to_csv())
```

```bash
# Запуск
python export_users.py

# Анализ в pandas
python -c "
import pandas as pd
df = pd.read_csv('relove_users.csv')
print(df.describe())
print(df['Gender'].value_counts())
print(df['Is Active'].value_counts())
"
```

---

## 🎉 Итого

Эти примеры покрывают:
- ✅ Первый запуск
- ✅ Регулярное обновление
- ✅ Импорт из конкретных каналов
- ✅ Тестирование
- ✅ Аналитика
- ✅ Фильтрация
- ✅ Поиск похожих
- ✅ Таргетированные рассылки
- ✅ Миграция данных
- ✅ Автоматизация
- ✅ Экспорт для анализа

**Выбирайте нужный сценарий и адаптируйте под свои задачи!** 🚀
