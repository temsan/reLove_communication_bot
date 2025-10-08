"""
Сервис для работы с глубинными метафизическими концептами.

Работает с:
- Планетарными историями
- Прошлыми жизнями
- Балансом света/тьмы
- Кармическими паттернами
"""
import logging
from typing import Dict, List, Optional
from enum import Enum

from relove_bot.services.llm_service import llm_service
from relove_bot.services.prompts import NATASHA_PROVOCATIVE_PROMPT

logger = logging.getLogger(__name__)


class PlanetaryType(str, Enum):
    """Типы планетарных историй."""
    LIGHT = "light"  # Световая планета
    DARK = "dark"  # Теневая планета
    BALANCED = "balanced"  # Балансная планета
    DESTROYED = "destroyed"  # Разрушенная планета
    UNKNOWN = "unknown"  # Неизвестно


class KarmicPattern(str, Enum):
    """Кармические паттерны."""
    VICTIM = "victim"  # Жертва
    RESCUER = "rescuer"  # Спаситель
    PERSECUTOR = "persecutor"  # Преследователь
    OBSERVER = "observer"  # Наблюдатель
    TRANSFORMER = "transformer"  # Трансформатор


class MetaphysicalService:
    """
    Сервис для работы с метафизическими концептами.
    Используется как вспомогательный инструмент, основные решения принимает LLM в диалоге.
    """
    
    METAPHYSICAL_ANALYSIS_PROMPT = """
Ты — эксперт по метафизике и кармическим паттернам в стиле Наташи Волкош.

САМ реши, что можешь определить из сообщений пользователя:

ПЛАНЕТАРНАЯ ИСТОРИЯ (если видишь признаки):
   - Тип планеты (световая/теневая/балансная/разрушенная)
   - Что произошло с планетой
   - Связь с текущей жизнью

КАРМИЧЕСКИЙ ПАТТЕРН (если очевиден):
   - Основной паттерн (жертва/спаситель/преследователь/наблюдатель/трансформатор)
   - Как проявляется сейчас

БАЛАНС СВЕТА/ТЬМЫ (если можешь оценить):
   - К чему тянет человека
   - Что нужно для баланса

КОРЕНЬ (если видишь):
   - Изначальная травма/обида

СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЯ:
{messages}

Ответь кратко, только то, что ДЕЙСТВИТЕЛЬНО видишь в сообщениях.
Не придумывай, если недостаточно данных.

Формат (включай только те пункты, которые можешь определить):
ПЛАНЕТА: [если видишь]
ПАТТЕРН: [если видишь]
БАЛАНС: [если видишь]
КОРЕНЬ: [если видишь]
МЕТАФОРА: [если подходит]
"""
    
    async def analyze_metaphysical_profile(
        self,
        messages: List[str],
        user_context: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Анализирует метафизический профиль пользователя.
        
        Args:
            messages: Список сообщений пользователя
            user_context: Дополнительный контекст пользователя
            
        Returns:
            dict: Метафизический профиль
        """
        if not messages:
            return {}
        
        # Объединяем сообщения
        messages_text = "\n".join([f"- {msg}" for msg in messages])
        
        # Формируем промпт
        prompt = self.METAPHYSICAL_ANALYSIS_PROMPT.format(messages=messages_text)
        
        try:
            response = await llm_service.analyze_text(
                prompt=prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=500
            )
            
            # Парсим ответ
            profile = self._parse_metaphysical_response(response)
            
            return profile
            
        except Exception as e:
            logger.error(f"Ошибка при анализе метафизического профиля: {e}")
            return {}
    
    def _parse_metaphysical_response(self, response: str) -> Dict[str, str]:
        """Парсит ответ LLM о метафизическом профиле."""
        profile = {
            "planetary_type": "unknown",
            "planetary_description": "",
            "karmic_pattern": "unknown",
            "pattern_manifestations": "",
            "balance": "",
            "metaphor": "",
            "transformation_path": "",
            "core_trauma": ""
        }
        
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("ПЛАНЕТА:"):
                parts = line.replace("ПЛАНЕТА:", "").strip().split(" - ", 1)
                if len(parts) >= 2:
                    profile["planetary_type"] = parts[0].strip().lower()
                    profile["planetary_description"] = parts[1].strip()
            elif line.startswith("ПАТТЕРН:"):
                parts = line.replace("ПАТТЕРН:", "").strip().split(" - ", 1)
                if len(parts) >= 2:
                    profile["karmic_pattern"] = parts[0].strip().lower()
                    profile["pattern_manifestations"] = parts[1].strip()
            elif line.startswith("БАЛАНС:"):
                profile["balance"] = line.replace("БАЛАНС:", "").strip()
            elif line.startswith("МЕТАФОРА:"):
                profile["metaphor"] = line.replace("МЕТАФОРА:", "").strip()
            elif line.startswith("ПУТЬ:"):
                profile["transformation_path"] = line.replace("ПУТЬ:", "").strip()
            elif line.startswith("КОРЕНЬ:"):
                profile["core_trauma"] = line.replace("КОРЕНЬ:", "").strip()
        
        return profile
    
    async def generate_provocative_question(
        self,
        metaphysical_profile: Dict[str, str],
        conversation_stage: str = "initial"
    ) -> str:
        """
        Генерирует провокативный вопрос на основе метафизического профиля.
        
        Args:
            metaphysical_profile: Метафизический профиль
            conversation_stage: Этап диалога (initial/deepening/core/transformation)
            
        Returns:
            str: Провокативный вопрос
        """
        if not metaphysical_profile:
            return "Расскажи о себе. Что сейчас происходит в твоей жизни?"
        
        # Формируем промпт для генерации вопроса
        prompt = f"""
{NATASHA_PROVOCATIVE_PROMPT}

МЕТАФИЗИЧЕСКИЙ ПРОФИЛЬ:
- Планета: {metaphysical_profile.get('planetary_type', 'unknown')}
- Описание планеты: {metaphysical_profile.get('planetary_description', '')}
- Кармический паттерн: {metaphysical_profile.get('karmic_pattern', 'unknown')}
- Проявления: {metaphysical_profile.get('pattern_manifestations', '')}
- Корень: {metaphysical_profile.get('core_trauma', '')}

ЭТАП ДИАЛОГА: {conversation_stage}

ЗАДАЧА:
Сгенерируй ОДИН короткий провокативный вопрос в стиле Наташи,
который поведёт человека глубже к осознанию корня проблемы.

Примеры стиля:
- "Почему он её выбрал?" (короткий прямой вопрос)
- "Война видишь? В твоем утверждении." (указание на паттерн)
- "И что?.. это смертельно?" (провокация на осознание)
- "Как долго еще нужно спасать тебя?" (вскрытие вампиризма)

Ответь ТОЛЬКО вопросом, без пояснений.
"""
        
        try:
            question = await llm_service.analyze_text(
                prompt=prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=50
            )
            
            return question.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации провокативного вопроса: {e}")
            return "..."
    
    async def analyze_core_trauma(
        self,
        metaphysical_profile: Dict[str, str],
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, str]:
        """
        Анализирует корневую травму на основе метафизического профиля и диалога.
        
        Args:
            metaphysical_profile: Метафизический профиль
            conversation_history: История диалога
            
        Returns:
            dict: Информация о корневой травме
        """
        # Формируем контекст диалога
        context = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in conversation_history
        ])
        
        prompt = f"""
{NATASHA_PROVOCATIVE_PROMPT}

МЕТАФИЗИЧЕСКИЙ ПРОФИЛЬ:
{metaphysical_profile}

ДИАЛОГ:
{context}

ЗАДАЧА:
Определи корневую травму человека. Ответь в формате:

ТРАВМА: [название травмы одним словом, например: "обида", "страх смерти", "чувство покинутости"]
ИСТОЧНИК: [откуда она пришла - планетарная история, детство, прошлая жизнь]
ПРОЯВЛЕНИЕ: [как проявляется сейчас в жизни]
ПУТЬ ИСЦЕЛЕНИЯ: [конкретное действие для принятия и трансформации]

Будь конкретен и прямолинеен.
"""
        
        try:
            response = await llm_service.analyze_text(
                prompt=prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=300
            )
            
            # Парсим ответ
            trauma_info = {}
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith("ТРАВМА:"):
                    trauma_info["trauma"] = line.replace("ТРАВМА:", "").strip()
                elif line.startswith("ИСТОЧНИК:"):
                    trauma_info["source"] = line.replace("ИСТОЧНИК:", "").strip()
                elif line.startswith("ПРОЯВЛЕНИЕ:"):
                    trauma_info["manifestation"] = line.replace("ПРОЯВЛЕНИЕ:", "").strip()
                elif line.startswith("ПУТЬ ИСЦЕЛЕНИЯ:"):
                    trauma_info["healing_path"] = line.replace("ПУТЬ ИСЦЕЛЕНИЯ:", "").strip()
            
            return trauma_info
            
        except Exception as e:
            logger.error(f"Ошибка при анализе корневой травмы: {e}")
            return {}
    
    async def generate_transformation_instruction(
        self,
        core_trauma: Dict[str, str],
        metaphysical_profile: Dict[str, str]
    ) -> str:
        """
        Генерирует конкретную инструкцию для трансформации.
        
        Args:
            core_trauma: Информация о корневой травме
            metaphysical_profile: Метафизический профиль
            
        Returns:
            str: Инструкция для трансформации
        """
        prompt = f"""
{NATASHA_PROVOCATIVE_PROMPT}

КОРНЕВАЯ ТРАВМА:
{core_trauma}

МЕТАФИЗИЧЕСКИЙ ПРОФИЛЬ:
{metaphysical_profile}

ЗАДАЧА:
Дай конкретную инструкцию для трансформации в стиле Наташи.
Короткую, прямую, максимум 3-4 предложения.

Примеры стиля:
"Попробуй сейчас отделиться от чувств и включить интеллект."
"Принять [страну], как могилу. Все худшее принять… В тишине. Не спасаться."
"Чайку попить. От поноса. А если не поможет, пусть все выйдет. Вместе с обидой."

Будь конкретен и практичен.
"""
        
        try:
            instruction = await llm_service.analyze_text(
                prompt=prompt,
                system_prompt=NATASHA_PROVOCATIVE_PROMPT,
                max_tokens=150
            )
            
            return instruction.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации инструкции: {e}")
            return ""


# Создаём глобальный экземпляр сервиса
metaphysical_service = MetaphysicalService()

