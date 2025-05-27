import pytest
import json
import asyncio
import logging
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any, List

# Настройка логирования для тестов
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Таймаут для тестов (в секундах)
TEST_TIMEOUT = 10.0

@pytest.fixture
def mock_llm_response():
    """Фикстура с мок-ответом от LLM."""
    return {
        "name": "Тестовый пользователь",
        "темы": ["осознанность", "медитация"],
        "эмоции": ["интерес", "энтузиазм"],
        "инсайты": ["Важно практиковать осознанность регулярно"],
        "вопросы": ["Как лучше внедрить практики в повседневную жизнь?"],
        "трудности": ["Сложно концентрироваться"],
        "рекомендации": ["рекомендуется продолжать практиковать осознанность"]
    }

@pytest.fixture
def mock_llm_service():
    """Фикстура с мок-сервисом LLM."""
    with patch('scripts.analyze_chat_llm.LLMService') as mock_llm_service:
        mock_llm = AsyncMock()
        mock_llm_service.return_value = mock_llm
        yield mock_llm

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_analyze_chat_structure(analyzer, test_chat_data, mock_llm_response, mock_llm_service):
    """Тестируем структуру возвращаемых данных анализа чата."""
    logger.info("Запуск теста test_analyze_chat_structure")
    # Настраиваем мок для _make_llm_request
    with patch.object(analyzer, '_make_llm_request', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = json.dumps(mock_llm_response)
        
        # Вызываем тестируемый метод
        result = await analyzer.analyze_chat(test_chat_data)
        
        # Проверяем структуру результата
        assert 'status' in result
        assert 'results' in result
        assert 'report' in result
        assert 'stats' in result
        assert result['status'] == 'success'
        
        # Проверяем, что мок был вызван с правильными аргументами
        mock_llm.assert_awaited()
        
        # Проверяем наличие ключевых полей в отчете
        report = result['report'].lower()
        assert 'общая статистика' in report
        assert 'анализ по участникам' in report
        assert 'рекомендации' in report

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_generate_text_report(analyzer, mock_llm_response):
    """Тестируем генерацию текстового отчета."""
    logger.info("Запуск теста test_generate_text_report")
    # Используем мок-ответ от LLM для создания тестовых данных
    test_results = {
        "user1": {
            "name": "Анна Иванова",
            "темы": ["осознанность", "медитация"],
            "эмоции": ["интерес", "энтузиазм"],
            "инсайты": ["Практика осознанности улучшает качество жизни"],
            "вопросы": ["Как внедрить практики в повседневную жизнь?"],
            "трудности": [],
            "рекомендации": ["продолжать практиковать осознанность"]
        }
    }
    
    # Генерируем отчет
    report = analyzer._generate_text_report(test_results)
    
    # Проверяем наличие ключевых разделов
    assert "АНАЛИЗ ЧАТА" in report
    assert "ОБЩАЯ СТАТИСТИКА" in report
    assert "АНАЛИЗ ПО УЧАСТНИКАМ" in report
    assert "Анна Иванова" in report
    
    # Проверяем форматирование рекомендаций
    assert "РЕКОМЕНДАЦИИ ДЛЯ РАБОТЫ С УЧАСТНИКОМ" in report
    assert "1. Продолжать практиковать осознанность" in report
    # Проверяем, что общих рекомендаций больше нет
    assert "ОБЩИЕ РЕКОМЕНДАЦИИ" not in report

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_empty_recommendations(analyzer):
    """Тестируем случай, когда рекомендации отсутствуют."""
    logger.info("Запуск теста test_empty_recommendations")
    test_results = {
        "user1": {
            "name": "Тестовый пользователь",
            "темы": [],
            "эмоции": [],
            "инсайты": [],
            "вопросы": [],
            "трудности": [],
            "рекомендации": []
        }
    }
    
    report = analyzer._generate_text_report(test_results)
    
    # Проверяем, что отображается сообщение об отсутствии рекомендаций
    assert "РЕКОМЕНДАЦИИ: не предоставлены" in report
    # Проверяем, что общих рекомендаций нет
    assert "ОБЩИЕ РЕКОМЕНДАЦИИ" not in report

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_error_handling(analyzer, mock_llm_service):
    """Тестируем обработку ошибок при анализе."""
    logger.info("Запуск теста test_error_handling")
    # Тест с пустыми данными
    with patch.object(analyzer, '_make_llm_request', new_callable=AsyncMock) as mock_llm:
        empty_result = await analyzer.analyze_chat({})
        assert 'error' in empty_result
        mock_llm.assert_not_called()  # Проверяем, что LLM не вызывался
    
    # Тест с неверным форматом данных
    with patch.object(analyzer, '_make_llm_request', new_callable=AsyncMock) as mock_llm:
        invalid_result = await analyzer.analyze_chat({"invalid": "data"})
        assert 'error' in invalid_result
        mock_llm.assert_not_called()  # Проверяем, что LLM не вызывался
    
    # Тест с ошибкой при вызове LLM
    with patch.object(analyzer, '_make_llm_request', new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("Ошибка API")
        error_result = await analyzer.analyze_chat({"messages": [{"text": "тест"}]})
        assert 'error' in error_result
        mock_llm.assert_awaited()  # Проверяем, что LLM был вызван
