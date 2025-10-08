import pytest
import json
import asyncio
import logging
from unittest.mock import AsyncMock, patch
from scripts.analyze_chat_llm import ChatAnalyzerLLM

# Настройка логирования для тестов
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Таймаут для тестов (в секундах)
TEST_TIMEOUT = 10.0

@pytest.fixture
def analyzer():
    return ChatAnalyzerLLM()

@pytest.fixture
def test_chat_data():
    return {
        "messages": [
            {"from_id": "user1", "from": "Иван Петров", "text": "Я пришёл за знаниями."},
            {"from_id": "user1", "from": "Иван Петров", "text": "Получил новые знакомства."},
            {"from_id": "user2", "from": "Анна Иванова", "text": "Хотела изменений в жизни."},
            {"from_id": "user2", "from": "Анна Иванова", "text": "Стала увереннее."}
        ]
    }

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_analyze_chat_tsv(analyzer, test_chat_data):
    """Проверяет, что анализ возвращает TSV с двумя ответами на пользователя."""
    # Мокаем llm_service.analyze_text, чтобы не делать реальные запросы
    mock_answers = [
        "1. Мотивация: получить знания.\n2. Результат: новые знакомства.",
        "1. Хотела изменений.\n2. Стала увереннее."
    ]
    with patch("relove_bot.services.llm_service.llm_service.analyze_text", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = lambda *a, **kw: mock_answers.pop(0)
        report = await analyzer.analyze_chat(test_chat_data)
        assert isinstance(report, str)
    lines = report.strip().splitlines()
    assert lines[0] == "Имя\tОтвет 1\tОтвет 2"
    assert lines[1].startswith("Иван Петров\t")
    assert lines[2].startswith("Анна Иванова\t")
    # Проверяем, что только две табуляции в строке пользователя
    assert lines[1].count("\t") == 2
    assert lines[2].count("\t") == 2
    # Нет структуры <АНАЛИЗ>
    assert "<АНАЛИЗ>" not in report
