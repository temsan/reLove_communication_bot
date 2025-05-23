"""
Тесты для ChatAnalyzerLLM
"""
import json
import pytest
from pathlib import Path
from scripts.analyze_chat_llm import ChatAnalyzerLLM

TEST_DATA = {
    "messages": [
        {
            "from_id": "user1",
            "from": "Анна",
            "date": "2023-05-15T20:05:00",
            "text": "Спасибо за ритуал! Очень мощная энергетика была, прям мурашки по коже!"
        },
        {
            "from_id": "user2",
            "from": "Мария",
            "date": "2023-05-15T20:07:00",
            "text": "А у меня не получилось подключиться, ссылка не работала. Как теперь посмотреть запись?"
        },
        {
            "from_id": "user3",
            "from": "Ольга",
            "date": "2023-05-15T20:10:00",
            "text": "Девочки, а когда будет следующий ритуал? Хочу снова поучаствовать!"
        }
    ]
}

@pytest.fixture
def analyzer():
    return ChatAnalyzerLLM()

@pytest.mark.asyncio
async def test_analyze_chat_basic(analyzer):
    """Тест базового анализа чата"""
    result = await analyzer.analyze_chat(TEST_DATA)
    
    # Проверяем базовую структуру ответа
    assert isinstance(result, dict), "Результат должен быть словарем"
    assert result["status"] == "success", f"Статус должен быть 'success', получено: {result.get('status')}"
    
    # Проверяем наличие основных разделов
    assert "results" in result, "Отсутствует раздел 'results'"
    assert "report" in result, "Отсутствует раздел 'report'"
    assert "stats" in result, "Отсутствует раздел 'stats'"
    
    # Проверяем содержимое разделов
    assert isinstance(result["results"], dict), "results должен быть словарем"
    assert isinstance(result["report"], str), f"report должен быть строкой, получено: {type(result['report'])}"
    assert isinstance(result["stats"], dict), "stats должен быть словарем"
    
    # Проверяем наличие обязательных полей в stats
    assert "total_messages" in result["stats"], "Отсутствует поле 'total_messages' в stats"
    assert result["stats"]["total_messages"] == len(TEST_DATA["messages"]), "Неверное количество сообщений"
    
    # Проверяем непустоту отчета
    assert len(result["report"].strip()) > 0, f"Отчет пустой. Полный результат: {result}"

@pytest.mark.asyncio
async def test_analyze_chat_empty():
    """Тест анализа пустого чата"""
    analyzer = ChatAnalyzerLLM()
    result = await analyzer.analyze_chat({"messages": []})
    assert "error" in result
    assert "Нет сообщений для анализа" in result["error"]

@pytest.mark.asyncio
async def test_analyze_chat_invalid():
    """Тест анализа с некорректными данными"""
    analyzer = ChatAnalyzerLLM()
    result = await analyzer.analyze_chat({"wrong_key": []})
    assert "error" in result
    assert "Нет сообщений для анализа" in result["error"]

@pytest.mark.asyncio
async def test_analyze_with_prompt_event(analyzer):
    """Тест анализа события"""
    messages = TEST_DATA["messages"]
    user_info = {"name": "Тестовый пользователь"}
    result = await analyzer._analyze_with_prompt(messages, user_info, "event")
    assert isinstance(result, dict)
    assert "темы" in result
    assert "эмоции" in result
    assert "инсайты" in result

@pytest.mark.asyncio
async def test_analyze_with_prompt_mirror(analyzer):
    """Тест зеркального анализа"""
    messages = TEST_DATA["messages"]
    user_info = {"name": "Тестовый пользователь"}
    result = await analyzer._analyze_with_prompt(messages, user_info, "mirror")
    assert isinstance(result, dict)
    assert "темы" in result
    assert "эмоции" in result
    assert "инсайты" in result

@pytest.mark.asyncio
async def test_analyze_with_prompt_relove(analyzer):
    """Тест ReLove анализа"""
    messages = TEST_DATA["messages"]
    user_info = {"name": "Тестовый пользователь"}
    result = await analyzer._analyze_with_prompt(messages, user_info, "relove")
    assert isinstance(result, dict)
    assert "темы" in result
    assert "эмоции" in result
    assert "инсайты" in result

def test_group_by_user(analyzer):
    """Тест группировки сообщений по пользователям"""
    result = analyzer._group_by_user(TEST_DATA["messages"])
    assert len(result) == 3
    assert "user1" in result
    assert "user2" in result
    assert "user3" in result
    assert len(result["user1"]) == 1
    assert len(result["user2"]) == 1
    assert len(result["user3"]) == 1

def test_get_default_analysis(analyzer):
    """Тест получения структуры анализа по умолчанию"""
    result = analyzer._get_default_analysis()
    assert isinstance(result, dict)
    assert "имя" in result
    assert "темы" in result
    assert "эмоции" in result
    assert "инсайты" in result
    assert "вопросы" in result
    assert "трудности" in result
    assert "рекомендации" in result
    assert all(isinstance(v, list) for k, v in result.items() if k != "имя")