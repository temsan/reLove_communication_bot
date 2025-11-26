# 🚀 Инструкция по fine-tuning модели Наташи на Kimi

**Документация Kimi**: https://platform.moonshot.ai/docs/guide/migrating-from-openai-to-kimi

**Совместимость**: Kimi имеет полную совместимость с OpenAI API

---

## 📋 Предварительные требования

1. **Kimi API ключ**
   - Получить на https://platform.moonshot.ai/
   - Добавить в `.env` файл: `KIMI_API_KEY=sk-...`

2. **Python 3.8+** с установленными зависимостями
   ```bash
   pip install openai python-dotenv
   ```

3. **Датасет** готов в формате JSONL
   - Файл: `data/natasha_finetuning_20251125_153356.jsonl`
   - 321 QA пара
   - Проверено и готово к использованию

---

## 🎯 Быстрый старт (3 шага)

### Шаг 1: Настройка .env

```bash
# Добавить в .env
KIMI_API_KEY=sk-...
```

### Шаг 2: Валидация датасета

```bash
python scripts/analysis/upload_and_finetune_kimi.py --validate-only
```

**Ожидаемый результат**:
```
✅ Validation passed: 321 training examples
```

### Шаг 3: Запуск fine-tuning

```bash
python scripts/analysis/upload_and_finetune_kimi.py
```

**Параметры по умолчанию**:
- Model: `moonshot-v1-8k`
- Epochs: `3`
- Learning rate: `0.1`
- Suffix: `natasha-v1`

**Ожидаемый результат**:
```
✅ File uploaded successfully to Kimi
   File ID: file-xxx

✅ Fine-tuning job created successfully in Kimi
   Job ID: ftjob-xxx
   Status: queued

⏳ Starting to monitor fine-tuning job...
```

---

## 🔧 Расширенные параметры

### Использование другой модели

```bash
python scripts/analysis/upload_and_finetune_kimi.py \
  --model moonshot-v1-32k \
  --epochs 5 \
  --learning-rate 0.05 \
  --suffix natasha-32k-v1
```

### Доступные модели Kimi

| Модель | Контекст | Описание |
|--------|----------|---------|
| `moonshot-v1-8k` | 8K | Базовая модель |
| `moonshot-v1-32k` | 32K | Расширенный контекст |
| `moonshot-v1-128k` | 128K | Максимальный контекст |

### Параметры

| Параметр | Значение | Описание |
|----------|----------|---------|
| `--file` | path | Путь к JSONL файлу |
| `--model` | moonshot-v1-8k | Базовая модель |
| `--epochs` | 3 | Количество эпох обучения |
| `--learning-rate` | 0.1 | Множитель learning rate |
| `--suffix` | natasha-v1 | Суффикс для имени модели |

### Режимы работы

```bash
# Только валидация
python scripts/analysis/upload_and_finetune_kimi.py --validate-only

# Только загрузка файла
python scripts/analysis/upload_and_finetune_kimi.py --upload-only

# Мониторинг существующего job
python scripts/analysis/upload_and_finetune_kimi.py --monitor ftjob-xxx

# Тестирование fine-tuned модели
python scripts/analysis/upload_and_finetune_kimi.py --test ft:moonshot-v1-8k:org-xxx::yyy

# Список всех jobs
python scripts/analysis/upload_and_finetune_kimi.py --list-jobs
```

---

## 💰 Стоимость

**Kimi обычно дешевле OpenAI**:

| Операция | Стоимость |
|----------|-----------|
| Fine-tuning | ~50% от OpenAI |
| Inference | ~30% от OpenAI |
| Хранение файлов | Бесплатно |

**Примерная стоимость для нашего датасета**:
- moonshot-v1-8k, 3 эпохи: ~$5-10
- moonshot-v1-32k, 3 эпохи: ~$10-15

---

## 🧪 Тестирование модели

### Автоматическое тестирование

После успешного fine-tuning скрипт автоматически протестирует модель:

```
Test 1: Я чувствую себя потерянным в жизни
Response: [ответ модели]

Test 2: Как начать свой бизнес?
Response: [ответ модели]

...
```

### Ручное тестирование

```bash
# Тестирование конкретной модели
python scripts/analysis/upload_and_finetune_kimi.py \
  --test ft:moonshot-v1-8k:org-xxx::yyy
```

### Тестирование в Python

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-...",
    base_url="https://api.moonshot.cn/v1"
)

response = client.chat.completions.create(
    model="ft:moonshot-v1-8k:org-xxx::yyy",  # Ваша fine-tuned модель
    messages=[
        {"role": "user", "content": "Я чувствую себя потерянным"}
    ],
    max_tokens=500,
    temperature=0.7
)

print(response.choices[0].message.content)
```

---

## 📊 Сравнение: OpenAI vs Kimi

| Параметр | OpenAI | Kimi |
|----------|--------|------|
| **API совместимость** | - | ✅ Полная |
| **Стоимость** | Базовая | ~50% дешевле |
| **Скорость** | Быстро | Быстро |
| **Качество** | Высокое | Высокое |
| **Контекст** | До 128K | До 128K |
| **Fine-tuning** | ✅ | ✅ |
| **Поддержка** | Хорошая | Хорошая |

---

## 🔄 Workflow

```
1. Валидация датасета
   ↓
2. Загрузка файла в Kimi
   ↓
3. Создание fine-tuning job
   ↓
4. Мониторинг прогресса (может занять часы)
   ↓
5. Получение fine-tuned модели
   ↓
6. Тестирование модели
   ↓
7. Использование в production
```

---

## ⚠️ Решение проблем

### Ошибка: "Invalid API key"

```bash
# Проверить, что KIMI_API_KEY установлен
echo $KIMI_API_KEY

# Добавить в .env
KIMI_API_KEY=sk-...
```

### Ошибка: "File validation failed"

```bash
# Переvalidировать файл
python scripts/analysis/upload_and_finetune_kimi.py --validate-only

# Проверить формат JSONL
head -1 data/natasha_finetuning_20251125_153356.jsonl | python -m json.tool
```

### Job зависает на "queued"

- Это нормально, может занять несколько минут
- Проверить статус в Kimi Dashboard
- Если зависает > 1 часа, отменить и пересоздать

### Низкое качество ответов

- Увеличить количество эпох (epochs)
- Уменьшить learning rate
- Добавить больше примеров в датасет
- Использовать более мощную модель (moonshot-v1-32k)

---

## 📝 Примеры использования

### Пример 1: Быстрое тестирование

```bash
# Валидация
python scripts/analysis/upload_and_finetune_kimi.py --validate-only

# Загрузка
python scripts/analysis/upload_and_finetune_kimi.py --upload-only

# Запуск с минимальными параметрами
python scripts/analysis/upload_and_finetune_kimi.py \
  --epochs 1 \
  --suffix natasha-test
```

### Пример 2: Продакшн fine-tuning

```bash
python scripts/analysis/upload_and_finetune_kimi.py \
  --model moonshot-v1-8k \
  --epochs 3 \
  --learning-rate 0.1 \
  --suffix natasha-prod-v1
```

### Пример 3: Использование 32K модели

```bash
python scripts/analysis/upload_and_finetune_kimi.py \
  --model moonshot-v1-32k \
  --epochs 3 \
  --learning-rate 0.1 \
  --suffix natasha-32k-v1
```

### Пример 4: Мониторинг существующего job

```bash
# Получить список всех jobs
python scripts/analysis/upload_and_finetune_kimi.py --list-jobs

# Мониторить конкретный job
python scripts/analysis/upload_and_finetune_kimi.py --monitor ftjob-xxx
```

### Пример 5: Тестирование модели

```bash
python scripts/analysis/upload_and_finetune_kimi.py \
  --test ft:moonshot-v1-8k:org-xxx::yyy
```

---

## 🎯 Преимущества Kimi

✅ **Дешевле** — ~50% от OpenAI  
✅ **Совместимо** — Используется OpenAI SDK  
✅ **Быстро** — Аналогичная скорость  
✅ **Качество** — Высокое качество ответов  
✅ **Контекст** — До 128K токенов  
✅ **Поддержка** — Хорошая техническая поддержка  

---

## 📚 Дополнительные ресурсы

- [Kimi Documentation](https://platform.moonshot.ai/docs)
- [Kimi API Reference](https://platform.moonshot.ai/docs/api-reference)
- [OpenAI SDK](https://github.com/openai/openai-python)
- [Kimi Pricing](https://platform.moonshot.ai/pricing)

---

## 🔗 Интеграция с OpenAI SDK

Kimi полностью совместим с OpenAI SDK:

```python
from openai import OpenAI

# OpenAI
client_openai = OpenAI(api_key="sk-...")

# Kimi (просто меняем base_url)
client_kimi = OpenAI(
    api_key="sk-...",
    base_url="https://api.moonshot.cn/v1"
)

# Остальной код идентичен!
response = client_kimi.chat.completions.create(
    model="moonshot-v1-8k",
    messages=[{"role": "user", "content": "..."}]
)
```

---

## 🎓 Следующие шаги

1. ✅ Датасет готов
2. ⏭️ Получить Kimi API ключ
3. ⏭️ Запустить fine-tuning
4. ⏭️ Дождаться завершения
5. ⏭️ Протестировать модель
6. ⏭️ Интегрировать в production
7. ⏭️ Мониторить качество

---

**Готово к использованию!** 🚀

Вопросы? Смотрите документацию Kimi или логи в `logs/finetune_kimi.log`
