from typing import List, Dict, Optional
from pydantic import BaseModel
from ..db.models import JourneyStageEnum

class StageDescription(BaseModel):
    name: str
    description: str
    emotional_triggers: List[str]
    psychological_impact: str
    questions: List[str]
    resistance_patterns: List[str]

# Определение характеристик для каждого этапа
JOURNEY_STAGES: Dict[JourneyStageEnum, StageDescription] = {
    JourneyStageEnum.ORDINARY_WORLD: StageDescription(
        name="Обычный мир",
        description="Показывает текущую ситуацию и проблемы пользователя",
        emotional_triggers=["дискомфорт", "неудовлетворенность", "рутина"],
        psychological_impact="Осознание текущих ограничений",
        questions=[
            "Что вас не устраивает в текущей ситуации?",
            "Какие ограничения вы чувствуете?",
            "Что бы вы хотели изменить?"
        ],
        resistance_patterns=["привычка", "страх перемен", "комфорт зоны"]
    ),
    JourneyStageEnum.CALL_TO_ADVENTURE: StageDescription(
        name="Зов к приключению",
        description="Предложение возможностей и изменений",
        emotional_triggers=["возможности", "изменения", "новые горизонты"],
        psychological_impact="Пробуждение интереса к изменениям",
        questions=[
            "Что бы вы хотели достичь?",
            "Какие возможности вас привлекают?",
            "Что мешает вам начать действовать?"
        ],
        resistance_patterns=["сомнения", "страх неизвестности"]
    ),
    JourneyStageEnum.REFUSAL: StageDescription(
        name="Отказ от призыва",
        description="Работа с сопротивлением и страхами",
        emotional_triggers=["страх", "неуверенность", "сомнения"],
        psychological_impact="Осознание и преодоление страхов",
        questions=[
            "Что вас останавливает?",
            "Какие страхи возникают?",
            "Что нужно, чтобы преодолеть эти страхи?"
        ],
        resistance_patterns=["рационализация", "откладывание"]
    ),
    JourneyStageEnum.MEETING_MENTOR: StageDescription(
        name="Встреча с наставником",
        description="Получение поддержки и инструментов",
        emotional_triggers=["поддержка", "направление", "инструменты"],
        psychological_impact="Уверенность в своих силах",
        questions=[
            "Какая поддержка вам нужна?",
            "Какие инструменты помогут вам?",
            "Кто может быть вашим наставником?"
        ],
        resistance_patterns=["недоверие", "зависимость"]
    ),
    JourneyStageEnum.CROSSING_THRESHOLD: StageDescription(
        name="Пересечение порога",
        description="Начало реальных действий",
        emotional_triggers=["действие", "изменения", "прогресс"],
        psychological_impact="Принятие ответственности за изменения",
        questions=[
            "Что вы готовы сделать прямо сейчас?",
            "Какой первый шаг вы можете сделать?",
            "Что поможет вам начать?"
        ],
        resistance_patterns=["прокрастинация", "перфекционизм"]
    ),
    JourneyStageEnum.TESTS_ALLIES_ENEMIES: StageDescription(
        name="Испытания, союзники, враги",
        description="Преодоление препятствий и поиск поддержки",
        emotional_triggers=["препятствия", "поддержка", "вызовы"],
        psychological_impact="Развитие навыков и отношений",
        questions=[
            "Какие препятствия вы встречаете?",
            "Кто может помочь вам?",
            "Как вы справляетесь с трудностями?"
        ],
        resistance_patterns=["изоляция", "отказ от помощи"]
    ),
    JourneyStageEnum.APPROACH: StageDescription(
        name="Приближение к сокровенной пещере",
        description="Подготовка к главному испытанию",
        emotional_triggers=["подготовка", "фокус", "намерение"],
        psychological_impact="Концентрация на цели",
        questions=[
            "К чему вы стремитесь?",
            "Что нужно для достижения цели?",
            "Как вы готовитесь к главному испытанию?"
        ],
        resistance_patterns=["рассеянность", "потеря фокуса"]
    ),
    JourneyStageEnum.ORDEAL: StageDescription(
        name="Испытание",
        description="Преодоление главного препятствия",
        emotional_triggers=["вызов", "преодоление", "трансформация"],
        psychological_impact="Личностный рост и трансформация",
        questions=[
            "Какое главное препятствие вы преодолеваете?",
            "Как вы справляетесь с трудностями?",
            "Что вы узнали о себе?"
        ],
        resistance_patterns=["отступление", "потеря веры"]
    ),
    JourneyStageEnum.REWARD: StageDescription(
        name="Награда",
        description="Получение результатов и осознание достижений",
        emotional_triggers=["успех", "достижение", "признание"],
        psychological_impact="Уверенность в своих силах",
        questions=[
            "Что вы достигли?",
            "Как вы себя чувствуете?",
            "Что вы получили в результате?"
        ],
        resistance_patterns=["недооценка достижений", "поиск новых проблем"]
    ),
    JourneyStageEnum.ROAD_BACK: StageDescription(
        name="Дорога назад",
        description="Интеграция изменений в обычную жизнь",
        emotional_triggers=["интеграция", "применение", "стабильность"],
        psychological_impact="Устойчивость изменений",
        questions=[
            "Как вы применяете полученный опыт?",
            "Что изменилось в вашей жизни?",
            "Как вы поддерживаете изменения?"
        ],
        resistance_patterns=["возврат к старым паттернам", "потеря мотивации"]
    ),
    JourneyStageEnum.RESURRECTION: StageDescription(
        name="Воскресение",
        description="Финальная трансформация и обновление",
        emotional_triggers=["трансформация", "обновление", "возрождение"],
        psychological_impact="Глубокое внутреннее изменение",
        questions=[
            "Как вы изменились?",
            "Что нового вы открыли в себе?",
            "Как вы видите себя теперь?"
        ],
        resistance_patterns=["неприятие изменений", "страх нового"]
    ),
    JourneyStageEnum.RETURN_WITH_ELIXIR: StageDescription(
        name="Возвращение с эликсиром",
        description="Делимся опытом и помогаем другим",
        emotional_triggers=["делиться", "помогать", "вдохновлять"],
        psychological_impact="Осмысление и передача опыта",
        questions=[
            "Чему вы научились?",
            "Как вы можете помочь другим?",
            "Какой опыт вы хотите передать?"
        ],
        resistance_patterns=["закрытость", "нежелание делиться"]
    )
} 