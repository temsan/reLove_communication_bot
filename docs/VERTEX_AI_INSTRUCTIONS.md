# 🚀 Fine-tuning на Google Vertex AI

**Документация**: https://cloud.google.com/vertex-ai/docs/generative-ai/models/gemini-supervised-tuning

---

## 📋 Требования

1. **Google Cloud Project** с включенным Vertex AI API
2. **Google Cloud Storage bucket** для хранения данных
3. **Google Cloud credentials** (установлены локально)
4. **Python 3.8+** с установленными зависимостями

---

## 🔧 Подготовка

### Шаг 1: Создать Google Cloud Project

1. Перейти на https://console.cloud.google.com/
2. Создать новый проект
3. Скопировать Project ID

### Шаг 2: Включить Vertex AI API

```bash
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage-api.googleapis.com
```

### Шаг 3: Создать Google Cloud Storage bucket

```bash
gsutil mb gs://natasha-finetuning-bucket
```

### Шаг 4: Установить Google Cloud SDK

```bash
# Windows
choco install google-cloud-sdk

# macOS
brew install --cask google-cloud-sdk

# Linux
curl https://sdk.cloud.google.com | bash
```

### Шаг 5: Аутентифицироваться

```bash
gcloud auth application-default login
```

---

## 🚀 Запуск Fine-tuning

### Команда

```bash
python scripts/analysis/upload_and_finetune_vertex.py \
  --project-id YOUR_PROJECT_ID \
  --bucket natasha-finetuning-bucket \
  --model gemini-1.5-pro-002 \
  --epochs 3 \
  --batch-size 4 \
  --learning-rate 0.001
```

### Параметры

| Параметр | Значение | Описание |
|----------|----------|---------|
| `--project-id` | YOUR_PROJECT_ID | Google Cloud Project ID |
| `--bucket` | natasha-finetuning-bucket | GCS bucket name |
| `--model` | gemini-1.5-pro-002 | Базовая модель |
| `--epochs` | 3 | Количество эпох |
| `--batch-size` | 4 | Размер батча |
| `--learning-rate` | 0.001 | Learning rate |

### Режимы

```bash
# Только валидация
python scripts/analysis/upload_and_finetune_vertex.py \
  --project-id YOUR_PROJECT_ID \
  --bucket natasha-finetuning-bucket \
  --validate-only

# Только загрузка
python scripts/analysis/upload_and_finetune_vertex.py \
  --project-id YOUR_PROJECT_ID \
  --bucket natasha-finetuning-bucket \
  --upload-only

# Мониторинг существующего job
python scripts/analysis/upload_and_finetune_vertex.py \
  --project-id YOUR_PROJECT_ID \
  --bucket natasha-finetuning-bucket \
  --monitor projects/YOUR_PROJECT_ID/locations/us-central1/pipelineJobs/JOB_ID
```

---

## 💰 Стоимость

| Операция | Стоимость |
|----------|-----------|
| Fine-tuning (1M tokens) | ~$10-20 |
| Inference (1M tokens) | ~$5-10 |
| Storage (per GB/month) | ~$0.02 |

**Примерная стоимость для нашего датасета**: ~$15-30

---

## ⏱️ Время

- **Подготовка**: ~10 минут
- **Fine-tuning**: ~1-2 часа
- **Тестирование**: ~5 минут

---

## 📊 Мониторинг

### В консоли

```bash
gcloud ai custom-jobs list --region=us-central1
gcloud ai custom-jobs describe JOB_ID --region=us-central1
```

### В Google Cloud Console

1. Перейти на https://console.cloud.google.com/vertex-ai
2. Выбрать "Training" → "Custom jobs"
3. Найти ваш job

---

## 🧪 Тестирование модели

После завершения fine-tuning:

```python
from google.cloud import aiplatform

# Инициализируем
aiplatform.init(project="YOUR_PROJECT_ID", location="us-central1")

# Получаем модель
model = aiplatform.Model("projects/YOUR_PROJECT_ID/locations/us-central1/models/MODEL_ID")

# Тестируем
response = model.predict(
    instances=[
        {
            "messages": [
                {"role": "user", "content": "Я чувствую себя потерянным"}
            ]
        }
    ]
)

print(response.predictions)
```

---

## ⚠️ Решение проблем

### Ошибка: "Permission denied"

```bash
gcloud auth application-default login
```

### Ошибка: "API not enabled"

```bash
gcloud services enable aiplatform.googleapis.com
```

### Ошибка: "Bucket not found"

```bash
gsutil mb gs://natasha-finetuning-bucket
```

### Job зависает

- Проверить логи в Cloud Console
- Убедиться, что у вас достаточно квоты
- Отменить job и пересоздать

---

## 📁 Файлы

- ⭐ `data/natasha_finetuning_20251125_153356.jsonl` — датасет
- 📝 `scripts/analysis/upload_and_finetune_vertex.py` — скрипт
- 📊 `data/vertex_finetune_config.json` — конфигурация

---

## 🎯 Следующие шаги

1. ✅ Датасет готов
2. ⏭️ Создать Google Cloud Project
3. ⏭️ Включить Vertex AI API
4. ⏭️ Создать GCS bucket
5. ⏭️ Установить Google Cloud SDK
6. ⏭️ Запустить fine-tuning
7. ⏭️ Дождаться завершения
8. ⏭️ Протестировать модель

---

## 📞 Поддержка

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Gemini Fine-tuning Guide](https://cloud.google.com/vertex-ai/docs/generative-ai/models/gemini-supervised-tuning)
- [Google Cloud Support](https://cloud.google.com/support)

---

**Готово!** Следуйте инструкциям выше для запуска fine-tuning на Vertex AI.
