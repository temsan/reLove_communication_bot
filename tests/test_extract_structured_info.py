"""
Тесты для метода _extract_structured_info_from_text из analyze_chat_llm.py
"""
import pytest
import json
from scripts.analyze_chat_llm import ChatAnalyzerLLM

@pytest.fixture
def analyzer():
    """Создаем экземпляр ChatAnalyzerLLM для тестирования"""
    return ChatAnalyzerLLM()

def test_extract_structured_info_empty_text(analyzer):
    """Проверка обработки пустого текста"""
    result = analyzer._extract_structured_info_from_text("")
    assert result == analyzer._get_default_analysis()

def test_extract_structured_info_with_topics(analyzer):
    """Проверка извлечения тем"""
    text = """
    Основные темы: 
    - Отношения
    - Карьера
    - Саморазвитие
    
    Эмоциональный тон: позитивный
    """
    result = analyzer._extract_structured_info_from_text(text)
    assert "forensic_analysis" in result
    assert "topics" in result["forensic_analysis"]
    assert "Отношения" in result["forensic_analysis"]["topics"]
    assert "позитивный" in result["forensic_analysis"]["sentiment"]

def test_extract_structured_info_with_emotions(analyzer):
    """Проверка извлечения эмоций"""
    text = """
    Эмоциональный тон: тревожный, неуверенный
    Ключевые эмоции: страх, беспокойство, надежда
    """
    result = analyzer._extract_structured_info_from_text(text)
    assert "forensic_analysis" in result
    assert "sentiment" in result["forensic_analysis"]
    assert "тревожный" in result["forensic_analysis"]["sentiment"]

def test_extract_structured_info_with_insights(analyzer):
    """Проверка извлечения инсайтов"""
    text = """
    Ключевые инсайты:
    1. Пользователь стремится к контролю в отношениях
    2. Имеются страхи перед одиночеством
    3. Выражено желание измениться
    """
    result = analyzer._extract_structured_info_from_text(text)
    assert "cognitive_analysis" in result
    assert "insights" in result["cognitive_analysis"]
    assert len(result["cognitive_analysis"]["insights"]) >= 3

def test_extract_structured_info_with_recommendations(analyzer):
    """Проверка извлечения рекомендаций"""
    text = """
    Рекомендации:
    - Практиковать осознанность
    - Пройти курс по управлению тревожностью
    - Обратиться к специалисту
    """
    result = analyzer._extract_structured_info_from_text(text)
    assert "transformation_advice" in result
    assert len(result["transformation_advice"]) >= 2

def test_extract_structured_info_complex(analyzer):
    """Комплексный тест с разными типами данных"""
    text = """
    Анализ сообщений пользователя:
    
    Основные темы:
    - Карьера и самореализация
    - Отношения с коллегами
    
    Эмоциональный фон: напряженный, с элементами тревожности
    
    Ключевые инсайты:
    1. Страх несоответствия ожиданиям
    2. Желание профессионального роста
    
    Рекомендации:
    - Развитие эмоционального интеллекта
    - Тренинг по управлению стрессом
    
    Когнитивные искажения:
    - Катастрофизация
    - Чтение мыслей
    """
    result = analyzer._extract_structured_info_from_text(text)
    
    # Проверяем наличие основных разделов
    assert "forensic_analysis" in result
    assert "cognitive_analysis" in result
    assert "transformation_advice" in result
    
    # Проверяем наполнение
    assert "Карьера" in " ".join(result["forensic_analysis"].get("topics", []))
    assert "напряженный" in result["forensic_analysis"].get("sentiment", "")
    assert "Страх несоответствия" in " ".join(result["cognitive_analysis"].get("insights", []))
    assert "эмоционального интеллекта" in " ".join(result["transformation_advice"])
    assert "Катастрофизация" in " ".join(result["cognitive_analysis"].get("distortions", []))
