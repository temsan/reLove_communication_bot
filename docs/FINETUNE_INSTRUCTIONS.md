# 🚀 Инструкция по fine-tuning модели Наташи

**Документация OpenAI**: https://platform.openai.com/docs/guides/supervised-fine-tuning

---

## 📋 Предварительные требования

1. **OpenAI API ключ** с доступом к fine-tuning
   - Получить на https://platform.openai.com/api-keys
   - Добавить в `.env` файл: `OPENAI_API_KEY=sk-...`

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

### Шаг 1: Валидация датасета

```bash
python scripts/analysis/upload_and_finetune_natasha.py --validate-only
```

**Ожидаемый результат**:
```
✅ Validation passed: 321 training examples
```

### Шаг 2: Загрузка и запуск fine-tuning

```bash
python scripts/analysis/upload_and_finetune_natasha.py
```

**Параметры по умолчанию**:
- Model: `gpt-4-turbo`
- Epochs: `3`
- Learning rate: `0.1`
- Suffix: `natasha-v1`

**Ожидаемый результат**:
```
✅ File uploaded successfully
   File ID: file-xxx

✅ Fine-tuning job created successfully
   Job ID: ftjob-xxx
   Status: queued

⏳ Starting to monitor fine-tuning job...
   (This may take several hours)
```

### Шаг 3: Мониторинг прогресса

Скрипт автоматически мониторит прогресс каждые 60 секунд.

**Статусы**:
- `queued` — ожидание начала
- `running` — идет обучение
- `succeeded` — успешно завершено ✅
- `failed` — ошибка ❌
- `cancelled` — отменено ⚠️

---

## 🔧 Расширенные параметры

### Использование другой модели

```bash
python scripts/analysis/upload_and_finetune_natasha.py \
  --model gpt-4-turbo \
  --epochs 5 \
  --learning-rate 0.05 \
  --suffix natasha-gpt4-v1
```

### Параметры

| Параметр | Значение | Описание |
|----------|----------|---------|
| `--file` | path | Путь к JSONL файлу |
| `--model` | gpt-3.5-turbo | Базовая модель |
| `--epochs` | 3 | Количество эпох обучения |
| `--learning-rate` | 0.1 | Множитель learning rate |
| `--suffix` | natasha-v1 | Суффикс для имени модели |

### Режимы работы

```bash
# Только валидация
python scripts/analysis/upload_and_finetune_natasha.py --validate-only

# Только загрузка файла
python scripts/analysis/upload_and_finetune_natasha.py --upload-only

# Мониторинг существующего job
python scripts/analysis/upload_and_finetune_natasha.py --monitor ftjob-xxx

# Тестирование fine-tuned модели
python scripts/analysis/upload_and_finetune_natasha.py --test ft:gpt-3.5-turbo:org-xxx::yyy

# Список всех jobs
python scripts/analysis/upload_and_finetune_natasha.py --list-jobs
```

---

## 📊 Рекомендуемые параметры

### Для быстрого тестирования

```bash
python scripts/analysis/upload_and_finetune_natasha.py \
  --epochs 1 \
  --learning-rate 0.2 \
  --suffix natasha-test
```

**Время**: ~30 минут  
**Стоимость**: ~$5-10

### Для продакшена

```bash
python scripts/analysis/upload_and_finetune_natasha.py \
  --epochs 3 \
  --learning-rate 0.1 \
  --suffix natasha-prod-v1
```

**Время**: ~2-3 часа  
**Стоимость**: ~$15-25

### Для максимального качества

```bash
python scripts/analysis/upload_and_finetune_natasha.py \
  --model gpt-4-turbo \
  --epochs 5 \
  --learning-rate 0.05 \
  --suffix natasha-premium-v1
```

**Время**: ~4-5 часов  
**Стоимость**: ~$50-100

---

## 💰 Стоимость

**Цены на fine-tuning** (за 1K токенов):

| Модель | Training | Input | Output |
|--------|----------|-------|--------|
| gpt-3.5-turbo | $0.03 | $0.0005 | $0.0015 |
| gpt-4-turbo | $0.06 | $0.01 | $0.03 |

**Примерная стоимость для нашего датасета**:
- gpt-3.5-turbo, 3 эпохи: ~$15-20
- gpt-4-turbo, 3 эпохи: ~$40-50

---

## 🧪 Тестирование модели

### Автоматическое тестирование

После успешного fine-tuning скрипт автоматически протестирует модель на 5 примерах:

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
python scripts/analysis/upload_and_finetune_natasha.py \
  --test ft:gpt-3.5-turbo:org-xxx::yyy
```

### Тестирование в Python

```python
from openai import OpenAI

client = OpenAI()

response = client.chat.completions.create(
    model="ft:gpt-3.5-turbo:org-xxx::yyy",  # Ваша fine-tuned модель
    messages=[
        {"role": "user", "content": "Я чувствую себя потерянным"}
    ],
    max_tokens=500,
    temperature=0.7
)

print(response.choices[0].message.content)
```

---

## 📈 Мониторинг в OpenAI Dashboard

1. Перейти на https://platform.openai.com/fine-tuning/jobs
2. Найти ваш job по ID
3. Смотреть статус и метрики в реальном времени

**Доступные метрики**:
- Training loss
- Validation loss
- Tokens processed
- Estimated time remaining

---

## ⚠️ Решение проблем

### Ошибка: "Invalid API key"

```bash
# Проверить, что OPENAI_API_KEY установлен
echo $OPENAI_API_KEY

# Добавить в .env
OPENAI_API_KEY=sk-...
```

### Ошибка: "File validation failed"

```bash
# Переvalidировать файл
python scripts/analysis/upload_and_finetune_natasha.py --validate-only

# Проверить формат JSONL
head -1 data/natasha_finetuning_20251125_153356.jsonl | python -m json.tool
```

### Job зависает на "queued"

- Это нормально, может занять несколько минут
- Проверить статус в OpenAI Dashboard
- Если зависает > 1 часа, отменить и пересоздать

### Низкое качество ответов

- Увеличить количество эпох (epochs)
- Уменьшить learning rate
- Добавить больше примеров в датасет
- Использовать более мощную базовую модель (gpt-4)

---

## 📝 Примеры использования

### Пример 1: Быстрое тестирование

```bash
# Валидация
python scripts/analysis/upload_and_finetune_natasha.py --validate-only

# Загрузка
python scripts/analysis/upload_and_finetune_natasha.py --upload-only

# Запуск с минимальными параметрами
python scripts/analysis/upload_and_finetune_natasha.py \
  --epochs 1 \
  --suffix natasha-test
```

### Пример 2: Продакшн fine-tuning

```bash
python scripts/analysis/upload_and_finetune_natasha.py \
  --model gpt-3.5-turbo \
  --epochs 3 \
  --learning-rate 0.1 \
  --suffix natasha-prod-v1
```

### Пример 3: Мониторинг существующего job

```bash
# Получить список всех jobs
python scripts/analysis/upload_and_finetune_natasha.py --list-jobs

# Мониторить конкретный job
python scripts/analysis/upload_and_finetune_natasha.py --monitor ftjob-xxx
```

### Пример 4: Тестирование модели

```bash
python scripts/analysis/upload_and_finetune_natasha.py \
  --test ft:gpt-3.5-turbo:org-xxx::yyy
```

---

## 🔄 Workflow

```
1. Валидация датасета
   ↓
2. Загрузка файла в OpenAI
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

## 📊 Ожидаемые результаты

После успешного fine-tuning модель должна:

✅ **Отвечать в стиле Наташи**
- Провокативные вопросы
- Поддерживающий тон
- Метафоры и образы

✅ **Работать с основными темами**
- Духовное развитие
- Отношения
- Бизнес
- Прошлые жизни

✅ **Сохранять контекст**
- Помнить предыдущие сообщения
- Давать связные ответы
- Развивать идеи

---

## 📚 Дополнительные ресурсы

- [OpenAI Fine-tuning Guide](https://platform.openai.com/docs/guides/supervised-fine-tuning)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Fine-tuning Best Practices](https://platform.openai.com/docs/guides/fine-tuning/best-practices)
- [Pricing](https://openai.com/pricing)

---

## 🎯 Следующие шаги

1. ✅ Датасет готов
2. ⏭️ Запустить fine-tuning
3. ⏭️ Дождаться завершения
4. ⏭️ Протестировать модель
5. ⏭️ Интегрировать в production
6. ⏭️ Мониторить качество

---

**Готово к использованию!** 🚀

Вопросы? Смотрите документацию OpenAI или логи в `logs/finetune_natasha.log`
