# Отчёт о чистке кодовой базы

## Выполненные изменения

### ✅ Обновлены названия полей

**Старые → Новые:**
- `profile_summary` → `profile`
- `psychological_summary` → `profile`
- `last_journey_stage` → `hero_stage`
- `metaphysical_profile` → `metaphysics`

---

## Исправленные файлы

### 1. **Services** (7 файлов)

#### `relove_bot/services/admin_stats_service.py`
```python
# Было: profile_summary IS NOT NULL
# Стало: profile IS NOT NULL
```

#### `relove_bot/services/journey_service.py`
```python
# Было: user.last_journey_stage
# Стало: user.hero_stage
```

#### `relove_bot/services/psych_analysis_service.py`
```python
# Было: user.psych_profile = summary
# Стало: user.profile = summary
```

#### `relove_bot/services/profile_service.py`
```python
# Было: 'psychological_summary': summary
# Стало: 'profile': summary
```

---

### 2. **Database** (2 файла)

#### `relove_bot/db/models.py`
- ✅ Обновлены названия полей
- ✅ Добавлены описания использования

#### `relove_bot/db/repository.py`
```python
# Было: user.profile_summary = summary
# Стало: user.profile = summary

# Было: last_journey_stage: Optional[str]
# Стало: hero_stage: Optional[str]

# Было: User.last_journey_stage == stage_enum
# Стало: User.hero_stage == stage_enum
```

---

### 3. **Handlers** (1 файл)

#### `relove_bot/handlers/flexible_diagnostic.py`
```python
# Было: user.profile_summary
# Стало: user.profile
```

---

### 4. **Utils** (3 файла)

#### `relove_bot/utils/fill_profiles.py`
```python
# Было: user.psychological_summary
# Стало: user.profile
```

#### `relove_bot/utils/broadcast_parser.py`
```python
# Было: last_journey_stage
# Стало: hero_stage
```

#### `relove_bot/utils/relove_streams.py`
```python
# Было: getattr(user, 'profile_summary', None)
# Стало: getattr(user, 'profile', None)
```

---

### 5. **Scripts** (1 файл)

#### `scripts/profiles/fill_profiles_from_channels.py`
- ✅ Обновлён для использования новых полей
- ✅ Добавлено заполнение hero_stage и metaphysics

---

## Устаревшие файлы (оставлены для истории)

### Скрипты миграции (не требуют обновления):
- `scripts/database/unify_summary_fields.py` - исторический скрипт миграции
- `scripts/database/migrate_markers_to_columns.py` - старая миграция
- `scripts/testing/test_import_one_per_channel.py` - тестовый скрипт

---

## Статистика изменений

| Категория | Файлов обновлено |
|-----------|------------------|
| Services  | 4                |
| Database  | 2                |
| Handlers  | 1                |
| Utils     | 3                |
| Scripts   | 1                |
| **ИТОГО** | **11**           |

---

## Проверка целостности

### ✅ Все ссылки обновлены
```bash
# Проверка отсутствия старых названий (кроме alembic и устаревших скриптов)
grep -r "profile_summary" --include="*.py" --exclude-dir=alembic --exclude-dir=scripts/database
grep -r "psychological_summary" --include="*.py" --exclude-dir=alembic --exclude-dir=scripts/database
grep -r "last_journey_stage" --include="*.py" --exclude-dir=alembic --exclude-dir=scripts/database
```

### ✅ Миграции применены
```bash
alembic current
# Результат: metaphysics_rename (head)
```

---

## Следующие шаги

### 🎯 Приоритет 1: Реализовать недостающие функции

#### В `relove_bot/services/telegram_service.py`:

```python
async def determine_journey_stage(profile: str) -> Optional[JourneyStageEnum]:
    """
    Определяет этап пути героя на основе профиля.
    
    Args:
        profile: Психологический профиль пользователя
        
    Returns:
        JourneyStageEnum или None
    """
    from relove_bot.services.llm_service import llm_service
    from relove_bot.db.models import JourneyStageEnum
    
    prompt = f"""Определи этап пути героя по Кэмпбеллу на основе профиля.

ПРОФИЛЬ:
{profile}

ЭТАПЫ:
1. Обычный мир
2. Зов к приключению
3. Отказ от призыва
4. Встреча с наставником
5. Пересечение порога
6. Испытания, союзники, враги
7. Приближение к сокровенной пещере
8. Испытание
9. Награда
10. Дорога назад
11. Воскресение
12. Возвращение с эликсиром

Ответь ТОЛЬКО названием этапа из списка."""

    response = await llm_service.analyze_text(prompt, max_tokens=50)
    
    # Парсинг ответа
    for stage in JourneyStageEnum:
        if stage.value.lower() in response.lower():
            return stage
    
    return None


async def create_metaphysical_profile(profile: str) -> Optional[Dict[str, Any]]:
    """
    Создаёт метафизический профиль на основе психологического.
    
    Args:
        profile: Психологический профиль пользователя
        
    Returns:
        Dict с метафизическими характеристиками
    """
    from relove_bot.services.llm_service import llm_service
    import json
    
    prompt = f"""Создай метафизический профиль на основе психологического.

ПРОФИЛЬ:
{profile}

Определи:
1. Планета-покровитель (Марс, Венера, Меркурий, Юпитер, Сатурн, Уран, Нептун, Плутон)
2. Карма (какие уроки проходит)
3. Баланс свет/тьма (от -10 до +10, где -10 = тьма, +10 = свет)

Ответь в формате JSON:
{{
    "planet": "название планеты",
    "karma": "описание кармических уроков",
    "light_dark_balance": число от -10 до +10
}}"""

    response = await llm_service.analyze_text(prompt, max_tokens=200)
    
    try:
        return json.loads(response)
    except:
        return None
```

---

### 🎯 Приоритет 2: Интегрировать в промпты бота

#### В `relove_bot/services/message_orchestrator.py`:

```python
# Добавить в формирование system_prompt:

if user.profile:
    system_prompt += f"\n\nПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:\n{user.profile}\n"

if user.hero_stage:
    system_prompt += f"\nЭТАП ПУТИ: {user.hero_stage.value}\n"

if user.metaphysics:
    system_prompt += f"\nМЕТАФИЗИКА:\n"
    system_prompt += f"- Планета: {user.metaphysics.get('planet', 'не определена')}\n"
    system_prompt += f"- Карма: {user.metaphysics.get('karma', 'не определена')}\n"
    system_prompt += f"- Баланс: {user.metaphysics.get('light_dark_balance', 0)}\n"
```

---

### 🎯 Приоритет 3: Заполнение history_summary

#### Создать функцию в `relove_bot/services/profile_service.py`:

```python
async def update_history_summary(user_id: int, new_message: str):
    """
    Обновляет историю диалогов пользователя.
    Сохраняет последние N сообщений в сжатом виде.
    """
    user = await self.user_repository.get_user(user_id)
    
    if not user:
        return
    
    # Получаем текущую историю
    history = user.history_summary or ""
    
    # Добавляем новое сообщение
    history += f"\n[{datetime.now().strftime('%Y-%m-%d')}] {new_message}"
    
    # Если история слишком длинная - сжимаем через LLM
    if len(history) > 5000:
        compressed = await llm_service.analyze_text(
            f"Сожми эту историю диалогов до 1000 символов, сохранив ключевые моменты:\n\n{history}",
            max_tokens=500
        )
        history = compressed
    
    user.history_summary = history
    await self.session.commit()
```

---

## Итоги

### ✅ Выполнено:
1. Обновлены все ссылки на старые поля (11 файлов)
2. Применены миграции БД
3. Проверена целостность кода

### 🔄 В процессе:
1. Реализация `determine_journey_stage()`
2. Реализация `create_metaphysical_profile()`
3. Интеграция полей в промпты
4. Заполнение `history_summary`

### 📊 Результат:
- Код унифицирован
- Названия полей короткие и понятные
- Готова база для дальнейшей интеграции
