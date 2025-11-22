# Руководство по обогащению профилей

## Обзор

Система автоматически обогащает профили пользователей, определяя:
- **hero_stage** - этап пути героя (12 этапов по Кэмпбеллу)
- **metaphysics** - метафизический профиль (планета, карма, баланс свет/тьма)
- **streams** - подходящие потоки reLove

## Архитектура

```
Посты + Био + Каналы
         ↓
    [LLM Analysis]
         ↓
      profile (Text)
         ↓
    [Enrichment]
    ↙    ↓    ↘
hero_stage  metaphysics  streams
```

## Компоненты

### 1. Profile Enrichment Service

**Файл:** `relove_bot/services/profile_enrichment.py`

**Функции:**

```python
async def determine_journey_stage(profile: str) -> Optional[JourneyStageEnum]
```
Определяет этап пути героя на основе профиля.

```python
async def create_metaphysical_profile(profile: str) -> Optional[Dict[str, Any]]
```
Создаёт метафизический профиль (планета, карма, баланс).

```python
async def determine_streams(profile: str) -> List[str]
```
Определяет подходящие потоки reLove.

---

### 2. Скрипт заполнения

**Файл:** `scripts/profiles/fill_profiles_from_channels.py`

**Использование:**

```bash
# Заполнить профили из всех каналов reLove
python scripts/profiles/fill_profiles_from_channels.py --all

# Заполнить из конкретного канала
python scripts/profiles/fill_profiles_from_channels.py --channel @relove

# Только импорт без заполнения профилей
python scripts/profiles/fill_profiles_from_channels.py --all --no-fill

# Инкрементальное обновление (только новые посты)
python scripts/profiles/fill_profiles_from_channels.py --all --incremental
```

**Что делает:**
1. Собирает участников из каналов reLove
2. Собирает их посты из всех каналов
3. Получает био и фото профиля
4. Создаёт психологический профиль через LLM
5. Обогащает профиль (hero_stage, metaphysics, streams)
6. Сохраняет в БД

---

### 3. Тестирование

**Файл:** `scripts/testing/test_profile_enrichment.py`

**Использование:**

```bash
# Тестировать все типы профилей
python scripts/testing/test_profile_enrichment.py --all

# Тестировать конкретный тип
python scripts/testing/test_profile_enrichment.py --profile beginner

# Тестировать реального пользователя
python scripts/testing/test_profile_enrichment.py --user 123456789
```

**Типы тестовых профилей:**
- `beginner` - новичок, только начинает путь
- `seeker` - ищущий, активно исследует
- `transformer` - трансформирующий, глубокая работа
- `dark_path` - тёмный путь, кризис
- `light_path` - светлый путь, трансляция любви
- `empty` - пустой профиль (edge case)

---

## Этапы пути героя

### 12 этапов по Кэмпбеллу:

1. **Обычный мир** - привычная реальность, рутина
2. **Зов к приключению** - первые проблески осознанности
3. **Отказ от призыва** - сопротивление, страхи
4. **Встреча с наставником** - готовность к поддержке
5. **Пересечение порога** - начало действий
6. **Испытания, союзники, враги** - преодоление препятствий
7. **Приближение к пещере** - подготовка к главному
8. **Испытание** - главное препятствие
9. **Награда** - получение результатов
10. **Дорога назад** - интеграция изменений
11. **Воскресение** - финальная трансформация
12. **Возвращение с эликсиром** - делимся опытом

---

## Метафизический профиль

### Планеты-покровители:

- **Марс** - воин, действие, агрессия
- **Венера** - любовь, красота, гармония
- **Меркурий** - коммуникация, интеллект
- **Юпитер** - расширение, мудрость, изобилие
- **Сатурн** - структура, ограничения, дисциплина
- **Уран** - революция, свобода, инновации
- **Нептун** - мистика, иллюзии, растворение
- **Плутон** - трансформация, смерть/возрождение, власть

### Баланс свет/тьма:

```
-10 ←─────────── 0 ─────────→ +10
Тьма          Баланс         Свет
```

- **-10 до -5**: глубокая тьма, саморазрушение
- **-4 до -1**: теневая сторона, работа с тьмой
- **0**: баланс, интеграция
- **+1 до +4**: световая сторона, рост
- **+5 до +10**: яркий свет, трансляция любви

---

## Потоки reLove

1. **Путь Героя** - трансформация через внутренний путь
2. **Прошлые Жизни** - работа с планетарными историями
3. **Открытие Сердца** - работа с любовью и принятием
4. **Трансформация Тени** - интеграция теневых частей
5. **Пробуждение** - выход из матрицы обыденности

---

## Примеры использования

### Пример 1: Заполнение профилей из каналов

```bash
# Полное заполнение всех пользователей из всех каналов reLove
python scripts/profiles/fill_profiles_from_channels.py --all

# Результат:
# - Собрано 500 пользователей из 5 каналов
# - Создано 500 профилей
# - Определено 450 hero_stage
# - Создано 430 metaphysics
# - Определено 480 streams
```

### Пример 2: Инкрементальное обновление

```bash
# Обновить только новые посты с последнего запуска
python scripts/profiles/fill_profiles_from_channels.py --all --incremental

# Результат:
# - Найдено 50 пользователей с новыми постами
# - Обновлено 50 профилей
# - Обновлено 45 hero_stage
```

### Пример 3: Тестирование

```bash
# Тестируем все типы профилей
python scripts/testing/test_profile_enrichment.py --all

# Результат:
# BEGINNER:
#   Hero Stage: Зов к приключению
#   Planet: Сатурн
#   Balance: -2
#   Streams: Путь Героя, Пробуждение
#
# SEEKER:
#   Hero Stage: Встреча с наставником
#   Planet: Меркурий
#   Balance: +3
#   Streams: Путь Героя, Открытие Сердца
#
# TRANSFORMER:
#   Hero Stage: Испытание
#   Planet: Плутон
#   Balance: +6
#   Streams: Трансформация Тени, Прошлые Жизни
```

### Пример 4: Тестирование реального пользователя

```bash
# Тестируем пользователя с ID 123456789
python scripts/testing/test_profile_enrichment.py --user 123456789

# Результат:
# User: Иван Иванов (@ivan)
# Current profile: Активный участник сообщества...
#
# 1. Determining journey stage...
# ✅ Hero stage: Пересечение порога
#
# 2. Creating metaphysical profile...
# ✅ Metaphysics:
#    Planet: Марс
#    Karma: Учится направлять энергию в созидание
#    Balance: +2
#
# 3. Determining streams...
# ✅ Streams: Путь Героя, Трансформация Тени
#
# ✅ User updated in database
```

---

## Интеграция в бота

### Использование в промптах

```python
# В relove_bot/services/message_orchestrator.py

system_prompt = "Ты Наташа Волкош..."

# Добавляем контекст профиля
if user.profile:
    system_prompt += f"\n\nПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:\n{user.profile}\n"

# Добавляем этап пути
if user.hero_stage:
    system_prompt += f"\nЭТАП ПУТИ: {user.hero_stage.value}\n"
    system_prompt += "Учитывай этот этап при формировании ответа.\n"

# Добавляем метафизику
if user.metaphysics:
    planet = user.metaphysics.get('planet', 'не определена')
    karma = user.metaphysics.get('karma', 'не определена')
    balance = user.metaphysics.get('light_dark_balance', 0)
    
    system_prompt += f"\nМЕТАФИЗИКА:\n"
    system_prompt += f"- Планета: {planet}\n"
    system_prompt += f"- Карма: {karma}\n"
    system_prompt += f"- Баланс свет/тьма: {balance}\n"

# Добавляем потоки
if user.streams:
    system_prompt += f"\nПОТОКИ: {', '.join(user.streams)}\n"
```

---

## Мониторинг и отладка

### Логи

Все операции логируются:

```python
logger.info(f"Determined hero_stage for user {user.id}: {hero_stage.value}")
logger.info(f"Created metaphysics for user {user.id}")
logger.info(f"Determined streams for user {user.id}: {streams}")
```

### Проверка в БД

```sql
-- Статистика по заполненности
SELECT 
    COUNT(*) as total_users,
    COUNT(profile) as with_profile,
    COUNT(hero_stage) as with_hero_stage,
    COUNT(metaphysics) as with_metaphysics,
    COUNT(streams) as with_streams
FROM users;

-- Распределение по этапам пути
SELECT hero_stage, COUNT(*) 
FROM users 
WHERE hero_stage IS NOT NULL 
GROUP BY hero_stage;

-- Распределение по планетам
SELECT metaphysics->>'planet' as planet, COUNT(*) 
FROM users 
WHERE metaphysics IS NOT NULL 
GROUP BY planet;

-- Распределение по балансу
SELECT 
    CASE 
        WHEN (metaphysics->>'light_dark_balance')::int < -5 THEN 'Глубокая тьма'
        WHEN (metaphysics->>'light_dark_balance')::int < 0 THEN 'Теневая сторона'
        WHEN (metaphysics->>'light_dark_balance')::int = 0 THEN 'Баланс'
        WHEN (metaphysics->>'light_dark_balance')::int < 5 THEN 'Световая сторона'
        ELSE 'Яркий свет'
    END as balance_category,
    COUNT(*)
FROM users 
WHERE metaphysics IS NOT NULL 
GROUP BY balance_category;
```

---

## Troubleshooting

### Проблема: LLM не определяет этап

**Причина:** Профиль слишком короткий или неинформативный

**Решение:**
```python
if not profile or len(profile) < 50:
    return None  # Пропускаем короткие профили
```

### Проблема: Неправильный JSON в metaphysics

**Причина:** LLM вернул невалидный JSON

**Решение:** Добавлена валидация и парсинг:
```python
try:
    start = response.find('{')
    end = response.rfind('}') + 1
    json_str = response[start:end]
    result = json.loads(json_str)
except json.JSONDecodeError:
    logger.warning("Could not parse JSON")
    return None
```

### Проблема: Слишком много токенов

**Причина:** Длинный профиль

**Решение:** Ограничиваем длину:
```python
profile[:2000]  # Первые 2000 символов
```

---

## Стоимость

### OpenAI API (gpt-4o-mini):

- **Определение hero_stage**: ~50 токенов = $0.000015
- **Создание metaphysics**: ~200 токенов = $0.00006
- **Определение streams**: ~100 токенов = $0.00003

**Итого на 1 пользователя:** ~$0.0001 (0.01 цента)

**На 1000 пользователей:** ~$0.10 (10 центов)

---

## Roadmap

### Ближайшие улучшения:

1. ✅ Реализовать базовое обогащение
2. ✅ Добавить тесты
3. ⏳ Интегрировать в промпты бота
4. ⏳ Добавить автоматическое обновление при новых постах
5. ⏳ Добавить векторизацию профилей (при базе >1000)

### Будущие фичи:

- Автоматическое предложение потоков на основе hero_stage
- Персонализация стиля общения на основе metaphysics
- Групповой подбор по совместимости планет
- Аналитика трансформации (изменение hero_stage со временем)
