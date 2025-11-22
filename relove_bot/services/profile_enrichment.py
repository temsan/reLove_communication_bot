"""
Сервис для обогащения профилей пользователей.
Определяет hero_stage, metaphysics, streams на основе profile.
"""
import logging
import json
from typing import Optional, Dict, Any, List
from relove_bot.db.models import JourneyStageEnum
from relove_bot.services.llm_service import llm_service

logger = logging.getLogger(__name__)


async def determine_journey_stage(profile: str) -> Optional[JourneyStageEnum]:
    """
    Определяет этап пути героя на основе профиля.
    
    Args:
        profile: Психологический профиль пользователя
        
    Returns:
        JourneyStageEnum или None
    """
    if not profile or len(profile) < 50:
        return None
    
    prompt = f"""Определи этап пути героя по Кэмпбеллу на основе профиля.

ПРОФИЛЬ:
{profile[:2000]}  # Ограничиваем для экономии токенов

ЭТАПЫ ПУТИ ГЕРОЯ:
1. Обычный мир - привычная реальность, рутина, дискомфорт
2. Зов к приключению - первые проблески осознанности, интерес к изменениям
3. Отказ от призыва - сопротивление, страхи, сомнения
4. Встреча с наставником - готовность получить поддержку
5. Пересечение порога - начало реальных действий
6. Испытания, союзники, враги - преодоление препятствий
7. Приближение к сокровенной пещере - подготовка к главному
8. Испытание - преодоление главного препятствия
9. Награда - получение результатов
10. Дорога назад - интеграция изменений
11. Воскресение - финальная трансформация
12. Возвращение с эликсиром - делимся опытом

Проанализируй профиль и определи текущий этап.
Ответь ТОЛЬКО названием этапа из списка выше (например: "Зов к приключению")."""

    try:
        response = await llm_service.analyze_text(prompt, max_tokens=50)
        
        if not response:
            return None
        
        response = response.strip().lower()
        
        # Парсинг ответа
        stage_mapping = {
            "обычный мир": JourneyStageEnum.ORDINARY_WORLD,
            "зов к приключению": JourneyStageEnum.CALL_TO_ADVENTURE,
            "отказ от призыва": JourneyStageEnum.REFUSAL,
            "встреча с наставником": JourneyStageEnum.MEETING_MENTOR,
            "пересечение порога": JourneyStageEnum.CROSSING_THRESHOLD,
            "испытания": JourneyStageEnum.TESTS_ALLIES_ENEMIES,
            "приближение": JourneyStageEnum.APPROACH,
            "испытание": JourneyStageEnum.ORDEAL,
            "награда": JourneyStageEnum.REWARD,
            "дорога назад": JourneyStageEnum.ROAD_BACK,
            "воскресение": JourneyStageEnum.RESURRECTION,
            "возвращение": JourneyStageEnum.RETURN_WITH_ELIXIR,
        }
        
        for key, stage in stage_mapping.items():
            if key in response:
                logger.info(f"Determined journey stage: {stage.value}")
                return stage
        
        logger.warning(f"Could not parse stage from response: {response}")
        return None
        
    except Exception as e:
        logger.error(f"Error determining journey stage: {e}")
        return None


async def create_metaphysical_profile(profile: str) -> Optional[Dict[str, Any]]:
    """
    Создаёт метафизический профиль на основе психологического.
    
    Args:
        profile: Психологический профиль пользователя
        
    Returns:
        Dict с метафизическими характеристиками или None
    """
    if not profile or len(profile) < 50:
        return None
    
    prompt = f"""Создай метафизический профиль на основе психологического.

ПРОФИЛЬ:
{profile[:2000]}  # Ограничиваем для экономии токенов

Определи:
1. Планета-покровитель (выбери одну):
   - Марс (воин, действие, агрессия)
   - Венера (любовь, красота, гармония)
   - Меркурий (коммуникация, интеллект)
   - Юпитер (расширение, мудрость, изобилие)
   - Сатурн (структура, ограничения, дисциплина)
   - Уран (революция, свобода, инновации)
   - Нептун (мистика, иллюзии, растворение)
   - Плутон (трансформация, смерть/возрождение, власть)

2. Карма (какие уроки проходит человек)

3. Баланс свет/тьма (от -10 до +10):
   - -10 до -5: глубокая тьма, саморазрушение
   - -4 до -1: теневая сторона, работа с тьмой
   - 0: баланс, интеграция
   - +1 до +4: световая сторона, рост
   - +5 до +10: яркий свет, трансляция любви

Ответь в формате JSON:
{{
    "planet": "название планеты",
    "karma": "описание кармических уроков (1-2 предложения)",
    "light_dark_balance": число от -10 до +10
}}"""

    try:
        response = await llm_service.analyze_text(prompt, max_tokens=200)
        
        if not response:
            return None
        
        # Пытаемся распарсить JSON
        try:
            # Ищем JSON в ответе
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                result = json.loads(json_str)
                
                # Валидация
                if 'planet' in result and 'karma' in result and 'light_dark_balance' in result:
                    # Проверяем баланс
                    balance = result['light_dark_balance']
                    if isinstance(balance, (int, float)) and -10 <= balance <= 10:
                        logger.info(f"Created metaphysical profile: {result['planet']}, balance={balance}")
                        return result
        except json.JSONDecodeError:
            pass
        
        logger.warning(f"Could not parse metaphysical profile from response: {response}")
        return None
        
    except Exception as e:
        logger.error(f"Error creating metaphysical profile: {e}")
        return None


async def determine_streams(profile: str) -> List[str]:
    """
    Определяет пройденные потоки reLove на основе профиля.
    
    Args:
        profile: Психологический профиль пользователя
        
    Returns:
        Список названий потоков
    """
    if not profile or len(profile) < 50:
        return []
    
    prompt = f"""Определи, какие потоки reLove подходят этому человеку на основе профиля.

ПРОФИЛЬ:
{profile[:2000]}

ПОТОКИ RELOVE:
1. Путь Героя - трансформация через прохождение внутреннего пути
2. Прошлые Жизни - работа с планетарными историями и кармой
3. Открытие Сердца - работа с любовью и принятием
4. Трансформация Тени - интеграция теневых частей личности
5. Пробуждение - выход из матрицы обыденности

Проанализируй профиль и определи 1-3 подходящих потока.
Ответь ТОЛЬКО названиями потоков через запятую (например: "Путь Героя, Трансформация Тени")."""

    try:
        response = await llm_service.analyze_text(prompt, max_tokens=100)
        
        if not response:
            return []
        
        # Парсим ответ
        available_streams = [
            "Путь Героя",
            "Прошлые Жизни",
            "Открытие Сердца",
            "Трансформация Тени",
            "Пробуждение"
        ]
        
        found_streams = []
        for stream in available_streams:
            if stream.lower() in response.lower():
                found_streams.append(stream)
        
        logger.info(f"Determined streams: {found_streams}")
        return found_streams
        
    except Exception as e:
        logger.error(f"Error determining streams: {e}")
        return []
