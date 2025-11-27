# 📊 Интеграция функционала в дашборд

Весь функционал анализа профиля и автоматических сообщений интегрирован в веб-дашборд.

---

## 🎯 API endpoints

### 1. Анализ профиля пользователя

```
POST /api/dashboard/analyze-user
```

**Параметры**:
```json
{
  "user_id": 123456789
}
```

**Ответ**:
```json
{
  "success": true,
  "analysis": {
    "emotional_state": "sadness",
    "energy_level": "medium",
    "focus_areas": ["relationships", "transformation"],
    "challenges": ["uncertainty", "fear"],
    "growth_indicators": ["awareness", "action"],
    "topic": "relationships"
  }
}
```

---

### 2. Генерация сообщения

```
POST /api/dashboard/generate-message
```

**Параметры**:
```json
{
  "user_id": 123456789
}
```

**Ответ**:
```json
{
  "success": true,
  "generated_message": "Вижу, что ты переживаешь...",
  "natasha_response": "Ответ Наташи...",
  "topic": "relationships"
}
```

---

### 3. Путь пользователя за период

```
POST /api/dashboard/user-journey
```

**Параметры**:
```json
{
  "user_id": 123456789,
  "period": "week"
}
```

**Периоды**:
- `yesterday` — вчера
- `week` — неделя
- `month` — месяц
- `3`, `7`, `30` — число дней

**Ответ**:
```json
{
  "success": true,
  "journey": [
    {
      "timestamp": "2025-11-27T10:30:00",
      "message": "На ритуале я почувствовала энергию",
      "response": "Ну вот ты и еще ближе...",
      "topic": "energy"
    }
  ],
  "consolidation": {
    "period": "week",
    "total_entries": 12,
    "topics": {
      "⚡ Энергия": 5,
      "💖 Отношения": 4
    },
    "date_range": {
      "from": "20.11.2025",
      "to": "27.11.2025"
    }
  }
}
```

---

### 4. Разделения пути пользователя

```
GET /api/dashboard/user-separations/{user_id}
```

**Ответ**:
```json
{
  "success": true,
  "separations": {
    "total_entries": 47,
    "by_topic": {
      "⚡ Энергия": 15,
      "💖 Отношения": 12,
      "🌙 Прошлые жизни": 10
    },
    "by_date": {
      "27.11.2025": 5,
      "26.11.2025": 3
    },
    "by_week": {
      "Неделя 48 (2025)": 12,
      "Неделя 47 (2025)": 10
    }
  }
}
```

---

## 🎨 Интеграция в HTML дашборда

### Кнопка анализа профиля

```html
<button onclick="analyzeUser(123456789)">
  📊 Анализировать профиль
</button>
```

### JavaScript функции

```javascript
// Анализ профиля
async function analyzeUser(userId) {
  const response = await fetch('/api/dashboard/analyze-user', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId })
  });
  const data = await response.json();
  console.log('Analysis:', data.analysis);
}

// Генерация сообщения
async function generateMessage(userId) {
  const response = await fetch('/api/dashboard/generate-message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId })
  });
  const data = await response.json();
  console.log('Generated:', data.generated_message);
  console.log('Response:', data.natasha_response);
}

// Получить путь за период
async function getUserJourney(userId, period = 'week') {
  const response = await fetch('/api/dashboard/user-journey', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, period: period })
  });
  const data = await response.json();
  console.log('Journey:', data.journey);
  console.log('Consolidation:', data.consolidation);
}

// Получить разделения
async function getUserSeparations(userId) {
  const response = await fetch(`/api/dashboard/user-separations/${userId}`);
  const data = await response.json();
  console.log('Separations:', data.separations);
}
```

---

## 📊 Анализ профиля

### Эмоциональное состояние

- **sadness** — грусть, печаль
- **joy** — радость, счастье
- **uncertainty** — поиск, вопросы
- **active** — энергия, активность
- **peaceful** — спокойствие, мир
- **neutral** — нейтральное

### Уровень энергии

- **high** — много активности
- **medium** — средняя активность
- **low** — низкая активность

### Области фокуса

- **energy** — энергетическая работа
- **relationships** — отношения
- **past_lives** — прошлые жизни
- **business** — бизнес
- **transformation** — трансформация

---

## 🚀 Использование в дашборде

### Для админа

1. Открыть дашборд
2. Выбрать пользователя
3. Нажать "Анализировать профиль"
4. Увидеть анализ состояния
5. Нажать "Генерировать сообщение"
6. Увидеть сгенерированное сообщение и ответ Наташи
7. Нажать "Путь за период"
8. Увидеть консолидацию пути

### Для пользователя (через бота)

```
/analyze_me — анализ профиля
/profile_state — показать анализ
/write_to_me — напиши мне сообщение
/my_journey — путь за период
/my_separations — разделения
```

---

## ✅ Чек-лист интеграции

- [x] API endpoints созданы
- [x] Анализ профиля работает
- [x] Генерация сообщений работает
- [x] Путь пользователя работает
- [x] Разделения работают
- [x] Документация готова

---

**Готово к использованию!** 🎉

