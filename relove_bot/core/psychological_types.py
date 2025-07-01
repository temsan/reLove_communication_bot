from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel
from ..db.models import PsychotypeEnum

class PersonalityTrait(BaseModel):
    name: str
    description: str
    triggers: List[str]  # Слова/фразы, которые вызывают реакцию
    emotional_responses: List[str]  # Возможные эмоциональные реакции

class PsychologicalProfile(BaseModel):
    type: PsychotypeEnum
    dominant_traits: List[PersonalityTrait]
    emotional_triggers: List[str]
    preferred_communication_style: str
    resistance_patterns: List[str]

# Определение характеристик для каждого типа
PSYCHOLOGICAL_TYPES: Dict[PsychotypeEnum, PsychologicalProfile] = {
    PsychotypeEnum.ANALYTICAL: PsychologicalProfile(
        type=PsychotypeEnum.ANALYTICAL,
        dominant_traits=[
            PersonalityTrait(
                name="Логическое мышление",
                description="Предпочитает структурированный подход и факты",
                triggers=["почему", "как это работает", "докажите"],
                emotional_responses=["сомнение", "потребность в доказательствах"]
            ),
            PersonalityTrait(
                name="Системность",
                description="Стремится к порядку и последовательности",
                triggers=["система", "структура", "процесс"],
                emotional_responses=["дискомфорт при неопределенности"]
            )
        ],
        emotional_triggers=["нелогичность", "отсутствие структуры"],
        preferred_communication_style="Факты, данные, логические аргументы",
        resistance_patterns=["эмоциональные манипуляции", "неструктурированная информация"]
    ),
    PsychotypeEnum.EMOTIONAL: PsychologicalProfile(
        type=PsychotypeEnum.EMOTIONAL,
        dominant_traits=[
            PersonalityTrait(
                name="Эмпатия",
                description="Сильно реагирует на эмоции других",
                triggers=["чувства", "эмоции", "переживания"],
                emotional_responses=["сопереживание", "эмоциональный отклик"]
            ),
            PersonalityTrait(
                name="Интуитивное понимание",
                description="Хорошо чувствует настроение и атмосферу",
                triggers=["атмосфера", "настроение", "энергия"],
                emotional_responses=["эмоциональное вовлечение"]
            )
        ],
        emotional_triggers=["эмоциональные истории", "личный опыт"],
        preferred_communication_style="Эмоциональные истории, личный опыт",
        resistance_patterns=["сухая логика", "отсутствие эмоциональной составляющей"]
    ),
    PsychotypeEnum.INTUITIVE: PsychologicalProfile(
        type=PsychotypeEnum.INTUITIVE,
        dominant_traits=[
            PersonalityTrait(
                name="Креативность",
                description="Стремится к новому и необычному",
                triggers=["инновации", "творчество", "возможности"],
                emotional_responses=["вдохновение", "любопытство"]
            ),
            PersonalityTrait(
                name="Видение",
                description="Смотрит в будущее и видит возможности",
                triggers=["будущее", "потенциал", "возможности"],
                emotional_responses=["энтузиазм", "предвкушение"]
            )
        ],
        emotional_triggers=["новые идеи", "возможности роста"],
        preferred_communication_style="Метафоры, образы, возможности",
        resistance_patterns=["рутина", "ограничения"]
    ),
    PsychotypeEnum.PRACTICAL: PsychologicalProfile(
        type=PsychotypeEnum.PRACTICAL,
        dominant_traits=[
            PersonalityTrait(
                name="Результативность",
                description="Фокусируется на конкретных результатах",
                triggers=["результат", "действие", "практика"],
                emotional_responses=["удовлетворение от достижений"]
            ),
            PersonalityTrait(
                name="Эффективность",
                description="Ищет оптимальные решения",
                triggers=["эффективность", "оптимизация", "решение"],
                emotional_responses=["удовлетворение от эффективности"]
            )
        ],
        emotional_triggers=["конкретные результаты", "практические решения"],
        preferred_communication_style="Конкретные шаги, практические советы",
        resistance_patterns=["теория без практики", "абстрактные концепции"]
    )
} 