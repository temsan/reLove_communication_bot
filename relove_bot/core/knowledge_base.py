from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class Psychotype(Enum):
    STRATEGIST = "Стратег"
    CREATOR = "Творец"
    GUARDIAN = "Хранитель"
    EXPLORER = "Исследователь"
    TRANSFORMER = "Трансформер"

class HeroJourneyStage(Enum):
    ORDINARY_WORLD = "Обычный мир"
    CALL_TO_ADVENTURE = "Зов к приключениям"
    REFUSAL_OF_CALL = "Отказ от зова"
    MEETING_WITH_MENTOR = "Встреча с наставником"
    CROSSING_FIRST_THRESHOLD = "Пересечение первого порога"

@dataclass
class PsychotypeDescription:
    name: str
    description: str
    strengths: List[str]
    challenges: List[str]
    emotional_triggers: List[str]  # Триггеры для эмоциональных реакций
    logical_patterns: List[str]    # Логические паттерны для нарушения

@dataclass
class JourneyStageDescription:
    name: str
    description: str
    current_state: str
    next_steps: List[str]
    emotional_state: str          # Текущее эмоциональное состояние
    resistance_points: List[str]  # Точки сопротивления для работы

# Описания психотипов
PSYCHOTYPES: Dict[Psychotype, PsychotypeDescription] = {
    Psychotype.STRATEGIST: PsychotypeDescription(
        name="Стратег",
        description="Вы видите мир как шахматную доску, где каждая фигура имеет свое значение. "
                   "Ваша сила в способности просчитывать ходы наперед и находить оптимальные решения.",
        strengths=[
            "Аналитическое мышление",
            "Стратегическое планирование",
            "Принятие взвешенных решений"
        ],
        challenges=[
            "Излишний контроль",
            "Сложность с импровизацией",
            "Перфекционизм"
        ],
        emotional_triggers=[
            "Страх неизвестного",
            "Потребность в безопасности",
            "Желание соответствовать нормам"
        ],
        logical_patterns=[
            "Дихотомическое мышление (хорошо/плохо)",
            "Линейная причинно-следственная связь",
            "Жесткие рамки восприятия реальности"
        ]
    ),
    Psychotype.CREATOR: PsychotypeDescription(
        name="Творец",
        description="Вы видите мир как чистый холст, готовый к воплощению ваших идей. "
                   "Ваша сила в способности создавать новое и вдохновлять других.",
        strengths=[
            "Креативное мышление",
            "Вдохновение других",
            "Создание нового"
        ],
        challenges=[
            "Незавершенность проектов",
            "Эмоциональные качели",
            "Сложность с рутиной"
        ],
        emotional_triggers=[
            "Жажда истины",
            "Внутренний конфликт",
            "Стремление к трансформации"
        ],
        logical_patterns=[
            "Поиск универсальных ответов",
            "Дуалистическое восприятие реальности",
            "Потребность в подтверждении"
        ]
    ),
    Psychotype.GUARDIAN: PsychotypeDescription(
        name="Хранитель",
        description="Вы видите мир как сад, который нужно бережно выращивать. "
                   "Ваша сила в способности создавать безопасное пространство для роста.",
        strengths=[
            "Эмпатия",
            "Забота о других",
            "Создание гармонии"
        ],
        challenges=[
            "Границы",
            "Самоотдача",
            "Принятие изменений"
        ],
        emotional_triggers=[
            "Стремление к единству",
            "Желание служить",
            "Глубокое принятие"
        ],
        logical_patterns=[
            "Холистическое восприятие",
            "Нелинейное мышление",
            "Интеграция противоположностей"
        ]
    )
}

# Описания этапов пути героя
JOURNEY_STAGES: Dict[HeroJourneyStage, JourneyStageDescription] = {
    HeroJourneyStage.ORDINARY_WORLD: JourneyStageDescription(
        name="Обычный мир",
        description="Вы находитесь в своей зоне комфорта, где все знакомо и предсказуемо. "
                   "Но внутри уже начинает зарождаться чувство, что что-то должно измениться.",
        current_state="Стабильность и рутина",
        next_steps=[
            "Осознание потребности в изменениях",
            "Исследование новых возможностей",
            "Подготовка к переменам"
        ],
        emotional_state="Неудовлетворенность и смутное беспокойство",
        resistance_points=[
            "Страх перемен",
            "Привычка к комфорту",
            "Социальное давление"
        ]
    ),
    HeroJourneyStage.CALL_TO_ADVENTURE: JourneyStageDescription(
        name="Зов к приключениям",
        description="Вы начинаете слышать внутренний голос, призывающий к изменениям. "
                   "Это может проявляться как неудовлетворенность текущей ситуацией или "
                   "внезапное вдохновение новыми идеями.",
        current_state="Пробуждение и интерес",
        next_steps=[
            "Исследование возможностей",
            "Поиск наставников и единомышленников",
            "Планирование первых шагов"
        ],
        emotional_state="Волнение и предвкушение",
        resistance_points=[
            "Сомнения в своих силах",
            "Боязнь последствий",
            "Неопределенность будущего"
        ]
    ),
    HeroJourneyStage.REFUSAL_OF_CALL: JourneyStageDescription(
        name="Отказ от зова",
        description="Несмотря на внутренний зов, вы пока сопротивляетесь изменениям. "
                   "Это нормальная реакция на страх перед неизвестным.",
        current_state="Сопротивление и сомнения",
        next_steps=[
            "Работа со страхами",
            "Поиск поддержки",
            "Малые шаги к изменениям"
        ],
        emotional_state="Страх и сопротивление",
        resistance_points=[
            "Сильный страх неизвестного",
            "Привязанность к старым паттернам",
            "Неверие в свои возможности"
        ]
    )
}

# Вопросы для диагностики
DIAGNOSTIC_QUESTIONS = [
    {
        "id": 1,
        "text": "Как вы относитесь к идее, что реальность может быть многомерной и не ограничиваться привычным восприятием?",
        "options": {
            "a": "Это звучит как фантастика, я предпочитаю опираться на проверенные факты",
            "b": "Интересная теория, которую стоит исследовать",
            "c": "Я уже ощущаю многомерность реальности в своем опыте"
        },
        "emotional_context": "Этот вопрос помогает понять готовность к трансформации восприятия реальности",
        "logical_context": "Исследует базовые убеждения о природе реальности"
    },
    {
        "id": 2,
        "text": "Что вы чувствуете, когда сталкиваетесь с ситуацией, которая нарушает ваши привычные представления о мире?",
        "options": {
            "a": "Дискомфорт и желание вернуться к привычному",
            "b": "Интерес и желание разобраться глубже",
            "c": "Возможность для роста и трансформации"
        },
        "emotional_context": "Помогает оценить эмоциональную реакцию на изменения",
        "logical_context": "Исследует гибкость мышления и адаптивность"
    },
    {
        "id": 3,
        "text": "Как вы работаете со своими эмоциями в сложных ситуациях?",
        "options": {
            "a": "Стараюсь контролировать и подавлять их",
            "b": "Пытаюсь понять их причину и трансформировать",
            "c": "Использую их как источник энергии для роста"
        },
        "emotional_context": "Исследует отношение к эмоциональной сфере",
        "logical_context": "Показывает уровень эмоционального интеллекта"
            },
            {
        "id": 4,
        "text": "Что для вас означает 'путь трансформации'?",
        "options": {
            "a": "Это что-то из области эзотерики, не для меня",
            "b": "Интересная возможность для личностного роста",
            "c": "Мой текущий жизненный путь и практика"
        },
        "emotional_context": "Помогает понять отношение к процессу трансформации",
        "logical_context": "Исследует готовность к изменениям"
            },
            {
        "id": 5,
        "text": "Как вы относитесь к идее баланса мужской и женской энергии внутри себя?",
        "options": {
            "a": "Не вижу в этом особого смысла",
            "b": "Интересная концепция, которую стоит изучить",
            "c": "Активно работаю над этим балансом"
        },
        "emotional_context": "Исследует отношение к интеграции полярностей",
        "logical_context": "Показывает понимание целостности"
    }
]

# Таблица маршрутизации к потокам
ROUTING_TABLE = {
    (Psychotype.STRATEGIST, HeroJourneyStage.ORDINARY_WORLD): {
        "stream": "Стратегическое планирование жизни",
        "description": "Научитесь применять свой стратегический ум для создания гармоничной жизни"
    },
    (Psychotype.STRATEGIST, HeroJourneyStage.CALL_TO_ADVENTURE): {
        "stream": "Трансформация через действие",
        "description": "Превратите свои стратегии в конкретные шаги к изменениям"
    },
    (Psychotype.CREATOR, HeroJourneyStage.ORDINARY_WORLD): {
        "stream": "Творческая трансформация",
        "description": "Раскройте свой творческий потенциал для создания новой реальности"
    },
    (Psychotype.CREATOR, HeroJourneyStage.CALL_TO_ADVENTURE): {
        "stream": "Воплощение идей",
        "description": "Научитесь воплощать свои творческие идеи в реальность"
    },
    (Psychotype.GUARDIAN, HeroJourneyStage.REFUSAL_OF_CALL): {
        "stream": "Границы и забота о себе",
        "description": "Научитесь заботиться о себе, сохраняя способность помогать другим"
    }
}

def analyze_answers(answers: Dict[int, str]) -> Tuple[Psychotype, HeroJourneyStage]:
    """
    Анализирует ответы пользователя и определяет его психотип и этап пути.
    
    Args:
        answers: Словарь с ответами пользователя, где ключ - ID вопроса,
                значение - выбранный вариант ответа
    
    Returns:
        Кортеж (психотип, этап пути)
    """
    psychotype_scores = {pt: 0 for pt in Psychotype}
    journey_scores = {stage: 0 for stage in HeroJourneyStage}
    
    for question_id, answer in answers.items():
        question = next(q for q in DIAGNOSTIC_QUESTIONS if q["id"] == question_id)
        option = next(opt for opt in question["options"] if opt["text"] == answer)
        
        points = option["points_to"]
        psychotype_scores[points["psychotype"]] += 1
        journey_scores[points["journey_stage"]] += 1
    
    # Определяем доминирующий психотип
    dominant_psychotype = max(psychotype_scores.items(), key=lambda x: x[1])[0]
    
    # Определяем доминирующий этап пути
    dominant_stage = max(journey_scores.items(), key=lambda x: x[1])[0]
    
    return dominant_psychotype, dominant_stage

def get_recommendation(psychotype: Psychotype, stage: HeroJourneyStage) -> Dict[str, str]:
    """
    Получает рекомендацию по потоку на основе психотипа и этапа пути.
    
    Args:
        psychotype: Определенный психотип пользователя
        stage: Определенный этап пути пользователя
    
    Returns:
        Словарь с информацией о рекомендуемом потоке
    """
    return ROUTING_TABLE.get((psychotype, stage), {
        "stream": "Базовый поток трансформации",
        "description": "Начните свой путь трансформации с основ"
    }) 