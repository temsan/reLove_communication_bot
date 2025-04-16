import pytest
from relove_bot.rag.llm import LLM
import base64

@pytest.mark.asyncio
async def test_analyze_content_text():
    llm = LLM()
    result = await llm.analyze_content(text="Привет, я люблю путешествовать и читать книги.")
    assert isinstance(result, dict)
    assert result["summary"]

@pytest.mark.asyncio
async def test_analyze_content_image_base64():
    llm = LLM()
    # Используем маленький png-файл-заглушку (1x1 px)
    png_stub = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
    result = await llm.analyze_content(image_base64=png_stub)
    assert isinstance(result, dict)
    assert result["summary"]

@pytest.mark.asyncio
async def test_analyze_content_text_and_image():
    llm = LLM()
    png_stub = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
    result = await llm.analyze_content(text="Девушка, 25 лет, любит спорт", image_base64=png_stub)
    assert isinstance(result, dict)
    assert result["summary"]

@pytest.mark.asyncio
async def test_analyze_content_error():
    llm = LLM()
    with pytest.raises(ValueError):
        await llm.analyze_content()  # Нет данных для анализа
