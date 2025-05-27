import pytest
import json
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.absolute()))

@pytest.fixture
def test_chat_data():
    """Фикстура с тестовыми данными чата."""
    return {
        "messages": [
            {
                "from_id": "user1",
                "from": {
                    "id": "user1",
                    "first_name": "Анна",
                    "last_name": "Иванова"
                },
                "date": "2025-05-24T12:30:00",
                "text": "Привет всем! Я вчера была на тренинге по осознанности, очень понравилось."
            },
            {
                "from_id": "user2",
                "from": {
                    "id": "user2",
                    "first_name": "Петр",
                    "last_name": "Сидоров"
                },
                "date": "2025-05-24T12:35:00",
                "text": "Привет! А у меня не получается медитировать, постоянно отвлекаюсь на мысли."
            },
            {
                "from_id": "user1",
                "from": {
                    "id": "user1",
                    "first_name": "Анна",
                    "last_name": "Иванова"
                },
                "date": "2025-05-24T12:36:00",
                "text": "Петр, это нормально! Главное не бороться с мыслями, а просто замечать их и возвращаться к дыханию."
            }
        ]
    }

@pytest.fixture
def analyzer():
    """Фикстура с инициализированным анализатором чата."""
    from scripts.analyze_chat_llm import ChatAnalyzerLLM
    return ChatAnalyzerLLM()
