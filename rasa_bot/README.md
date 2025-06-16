# Чат-бот на Rasa

Этот проект представляет собой интеграцию чат-бота на базе Rasa в ваш основной проект.

## Установка

1. Убедитесь, что у вас установлен Python 3.8 или выше
2. Установите зависимости:
   ```bash
   pip install -r ../requirements.txt
   ```
3. Установите модель для spaCy:
   ```bash
   python -m spacy download en_core_web_md
   ```

## Обучение модели

Для обучения модели выполните:

```bash
rasa train
```

## Запуск

1. Запустите сервер действий (actions server):
   ```bash
   rasa run actions
   ```

2. В другом терминале запустите Rasa shell для тестирования:
   ```bash
   rasa shell
   ```

## Интеграция с проектом

Для интеграции с вашим проектом используйте Rasa SDK:

```python
from rasa.core.agent import Agent

# Загрузка обученной модели
agent = Agent.load("models")

# Обработка сообщения
async def handle_message(message: str, sender_id: str = "user"):
    response = await agent.handle_text(message, sender_id=sender_id)
    return response
```

## Настройка

- `config.yml` - конфигурация пайплайна и политик
- `domain.yml` - домен бота (интенты, сущности, ответы, действия)
- `data/` - данные для обучения (NLU, stories, rules)
- `actions/` - кастомные действия
- `endpoints.yml` - настройки конечных точек

## Дополнительные команды

- Обучение и оценка модели:
  ```bash
  rasa train
  rasa test
  ```

- Запуск с визуализацией:
  ```bash
  rasa visualize
  ```

- Запуск API сервера:
  ```bash
  rasa run --enable-api --cors "*"
  ```

## Документация

- [Документация Rasa](https://rasa.com/docs/rasa/)
- [Rasa SDK](https://rasa.com/docs/action-server/)
- [Rasa X](https://rasa.com/docs/rasa-x/)
