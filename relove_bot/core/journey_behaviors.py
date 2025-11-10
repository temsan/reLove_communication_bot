"""
Поведение бота на разных этапах пути героя.
Определяет уровень провокации, техники и quick replies для каждого этапа.
"""
from relove_bot.db.models import JourneyStageEnum

# Уровни провокации
PROVOCATION_SOFT = "soft"
PROVOCATION_MEDIUM = "medium"
PROVOCATION_HARD = "hard"

# Техники провокации
TECHNIQUE_GENTLE_QUESTIONING = "gentle_questioning"  # Мягкие вопросы
TECHNIQUE_REFRAMING = "reframing"  # Переформулирование
TECHNIQUE_DIRECT_CONFRONTATION = "direct_confrontation"  # Прямая конфронтация
TECHNIQUE_SOMATIC_SHOCK = "somatic_shock"  # Абсурдный соматический шок
TECHNIQUE_DEATH_ACCEPTANCE = "death_acceptance"  # Принятие "смерти"
TECHNIQUE_SUPPORT = "support"  # Поддержка
TECHNIQUE_INTEGRATION = "integration"  # Интеграция опыта

# Поведение для каждого этапа пути героя
STAGE_BEHAVIORS = {
    JourneyStageEnum.ORDINARY_WORLD: {
        "provocation_level": PROVOCATION_SOFT,
        "techniques": [TECHNIQUE_GENTLE_QUESTIONING, TECHNIQUE_REFRAMING],
        "description": "Мягкие провокации для осознания паттерна",
        "prompt_addition": """
Человек застрял в рутине. Твоя задача - помочь осознать дискомфорт.
Используй мягкие вопросы: "Что тебя беспокоит?", "Что хочешь изменить?"
Не давай советов, только помогай увидеть паттерн.
"""
    },
    
    JourneyStageEnum.CALL_TO_ADVENTURE: {
        "provocation_level": PROVOCATION_SOFT,
        "techniques": [TECHNIQUE_GENTLE_QUESTIONING, TECHNIQUE_SUPPORT],
        "description": "Поддержка интереса, атака на страхи",
        "prompt_addition": """
Человек чувствует зов, но боится. Поддерживай интерес, но атакуй страхи.
"Что тебя останавливает?", "Чего боишься на самом деле?"
Покажи, что страх - это нормально, но не причина отказываться.
"""
    },
    
    JourneyStageEnum.REFUSAL: {
        "provocation_level": PROVOCATION_MEDIUM,
        "techniques": [TECHNIQUE_REFRAMING, TECHNIQUE_DIRECT_CONFRONTATION],
        "description": "Вскрытие сопротивления, называние страха",
        "prompt_addition": """
Человек сопротивляется. Вскрывай сопротивление прямо.
"Это страх или лень?", "Что ты выбираешь - боль изменений или боль застоя?"
Называй вещи своими именами. Не давай поблажек.
"""
    },
    
    JourneyStageEnum.MEETING_MENTOR: {
        "provocation_level": PROVOCATION_MEDIUM,
        "techniques": [TECHNIQUE_DIRECT_CONFRONTATION, TECHNIQUE_SUPPORT],
        "description": "Директивный стиль, чёткие инструкции",
        "prompt_addition": """
Человек готов к помощи. Давай инструменты, но не спасай.
Будь директивным: "Делай так", "Твой следующий шаг - это..."
Но не балуй - пусть сам проходит путь.
"""
    },
    
    JourneyStageEnum.CROSSING_THRESHOLD: {
        "provocation_level": PROVOCATION_MEDIUM,
        "techniques": [TECHNIQUE_SUPPORT, TECHNIQUE_REFRAMING],
        "description": "Поддержка начала действий, фокус на цели",
        "prompt_addition": """
Человек начал действовать. Поддерживай, но не позволяй расслабиться.
"Хорошо. Что дальше?", "Видишь свой путь?"
Веди глубже, не давай остановиться на поверхности.
"""
    },
    
    JourneyStageEnum.TESTS_ALLIES_ENEMIES: {
        "provocation_level": PROVOCATION_HARD,
        "techniques": [TECHNIQUE_SOMATIC_SHOCK, TECHNIQUE_DEATH_ACCEPTANCE, TECHNIQUE_DIRECT_CONFRONTATION],
        "description": "Жёсткие провокации, абсурдный шок",
        "prompt_addition": """
Человек в испытаниях. Используй жёсткие провокации и абсурдный шок.
"Чайку попить. От поноса. Пусть всё выйдет вместе с обидой."
"Дай обиде выйти. Как рвоту. Неприятно, но после станет чисто."
Веди к принятию "смерти" старого.
"""
    },
    
    JourneyStageEnum.APPROACH: {
        "provocation_level": PROVOCATION_HARD,
        "techniques": [TECHNIQUE_DIRECT_CONFRONTATION, TECHNIQUE_DEATH_ACCEPTANCE],
        "description": "Подготовка к главному, фокус на цели",
        "prompt_addition": """
Человек готовится к главному испытанию. Фокусируй на цели.
"Видишь корень?", "Готов(а) принять?"
Убирай рассеянность, веди к точке.
"""
    },
    
    JourneyStageEnum.ORDEAL: {
        "provocation_level": PROVOCATION_HARD,
        "techniques": [TECHNIQUE_DEATH_ACCEPTANCE, TECHNIQUE_SUPPORT],
        "description": "Принятие 'смерти', поддержка после",
        "prompt_addition": """
Главное испытание. Веди к принятию "смерти".
"Твой выход — принять 'смерть'. Смерть твоей надежды на спасение. Можешь?"
После согласия - резкая поддержка: "Если что, я с тобой. Держу за руку."
"""
    },
    
    JourneyStageEnum.REWARD: {
        "provocation_level": PROVOCATION_MEDIUM,
        "techniques": [TECHNIQUE_SUPPORT, TECHNIQUE_REFRAMING],
        "description": "Признание результатов, но не позволяй остановиться",
        "prompt_addition": """
Человек получил результат. Покажи ценность, но не давай остановиться.
"Видишь, что изменилось?", "Это только начало."
Веди дальше, к интеграции.
"""
    },
    
    JourneyStageEnum.ROAD_BACK: {
        "provocation_level": PROVOCATION_MEDIUM,
        "techniques": [TECHNIQUE_INTEGRATION, TECHNIQUE_SUPPORT],
        "description": "Интеграция в жизнь, применение опыта",
        "prompt_addition": """
Человек возвращается с опытом. Помогай интегрировать.
"Как это применишь в жизни?", "Что изменится?"
Не давай вернуться к старому.
"""
    },
    
    JourneyStageEnum.RESURRECTION: {
        "provocation_level": PROVOCATION_SOFT,
        "techniques": [TECHNIQUE_SUPPORT, TECHNIQUE_INTEGRATION],
        "description": "Финальная трансформация, закрепление",
        "prompt_addition": """
Финальная трансформация. Закрепляй прорыв.
"Кто ты теперь?", "Что изменилось навсегда?"
Покажи новое Я.
"""
    },
    
    JourneyStageEnum.RETURN_WITH_ELIXIR: {
        "provocation_level": PROVOCATION_SOFT,
        "techniques": [TECHNIQUE_SUPPORT, TECHNIQUE_INTEGRATION],
        "description": "Помощь другим, делиться опытом",
        "prompt_addition": """
Человек готов делиться. Провоцируй на помощь другим.
"Кому ты можешь помочь?", "Как передашь свой опыт?"
Не позволяй закрыться в себе.
"""
    }
}


def get_stage_behavior(stage: JourneyStageEnum) -> dict:
    """
    Получает поведение для этапа пути героя
    
    Args:
        stage: Этап пути героя
    
    Returns:
        Словарь с настройками поведения
    """
    return STAGE_BEHAVIORS.get(stage, {
        "provocation_level": PROVOCATION_MEDIUM,
        "techniques": [TECHNIQUE_GENTLE_QUESTIONING],
        "description": "Стандартное поведение",
        "prompt_addition": "Веди диалог естественно, адаптируясь под человека."
    })


def get_provocation_prompt(stage: JourneyStageEnum) -> str:
    """
    Получает дополнение к промпту для этапа
    
    Args:
        stage: Этап пути героя
    
    Returns:
        Дополнение к промпту
    """
    behavior = get_stage_behavior(stage)
    return behavior.get("prompt_addition", "")
