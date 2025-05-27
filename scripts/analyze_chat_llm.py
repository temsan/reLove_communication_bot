"""
Модуль для анализа чата с помощью LLM.
Анализирует сообщения из чата reLove, выделяя ключевые темы, эмоции и инсайты.
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import time
import traceback
import warnings
import argparse
import httpx
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from tqdm import tqdm
from dotenv import load_dotenv

class AnalysisCache:
    """Класс для кеширования результатов анализа."""
    
    def __init__(self, cache_dir: str = ".analysis_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_index = self._load_index()
    
    def _load_index(self) -> Dict[str, str]:
        """Загружает индекс кеша."""
        index_path = self.cache_dir / "index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def _save_index(self):
        """Сохраняет индекс кеша."""
        index_path = self.cache_dir / "index.json"
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache_index, f, ensure_ascii=False, indent=2)
    
    def _get_user_hash(self, user_id: str, messages: list) -> str:
        """Генерирует хеш для пользователя на основе его ID и сообщений."""
        data = f"{user_id}:{len(messages)}:{messages[0].get('date', '') if messages else ''}:{messages[-1].get('date', '') if messages else ''}"
        return hashlib.md5(data.encode('utf-8')).hexdigest()
    
    def get_cached_result(self, user_id: str, messages: list) -> Optional[Dict[str, Any]]:
        """Пытается получить закешированный результат для пользователя."""
        user_hash = self._get_user_hash(user_id, messages)
        cache_file = self.cache_dir / f"{user_hash}.json"
        
        if user_hash in self.cache_index and cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None
    
    def save_result(self, user_id: str, messages: list, result: Dict[str, Any]) -> str:
        """Сохраняет результат анализа в кеш."""
        user_hash = self._get_user_hash(user_id, messages)
        cache_file = self.cache_dir / f"{user_hash}.json"
        
        # Добавляем метаданные
        result_with_meta = {
            "user_id": user_id,
            "cached_at": datetime.now().isoformat(),
            "messages_count": len(messages),
            "first_message_date": messages[0].get('date', '') if messages else '',
            "last_message_date": messages[-1].get('date', '') if messages else '',
            "data": result
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result_with_meta, f, ensure_ascii=False, indent=2)
            
            # Обновляем индекс
            self.cache_index[user_id] = user_hash
            self._save_index()
            return str(cache_file)
        except IOError as e:
            logger.error(f"Ошибка при сохранении в кеш: {e}")
            return ""

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.append(str(Path(__file__).parent.parent))
from relove_bot.config import settings
from relove_bot.services.prompts import PSYCHOLOGICAL_ANALYSIS_PROMPT

# Настройка логирования
logger = logging.getLogger()
logger.setLevel(logging.INFO)  # Устанавливаем уровень логирования

# Удаляем все существующие обработчики
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Создаем форматтер для файла
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Настраиваем обработчик для вывода в файл
file_handler = logging.FileHandler('chat_analysis.log', mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Настраиваем обработчик для вывода в консоль с упрощенным форматом
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # В консоль выводим только INFO и выше
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Отключаем вывод сообщений от внешних библиотек
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Отключаем предупреждения transformers
warnings.filterwarnings("ignore", category=FutureWarning)

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from relove_bot.services.llm_service import LLMService
from relove_bot.services.prompts import PSYCHOLOGICAL_ANALYSIS_PROMPT
from relove_bot.config import settings

# Добавляем фильтр для исключения сообщений пользователей и деталей запросов
class MessageFilter(logging.Filter):
    def filter(self, record):
        return not any(keyword in record.getMessage().lower() for keyword in [
            'сообщение:', 'текст:', 'user:', 'пользователь:', 'message:', 'text:',
            '=== детали запроса к llm ===', 'url:', 'модель:', 'размер промпта:',
            '=== настройки llmservice ===', 'api base:', 'api key:', 'model:',
            'неожиданный формат ответа:', 'ошибка парсинга json:', 'получен ответ:',
            'rate limit exceeded:', 'error:', 'ошибка:'
        ])

logger.addFilter(MessageFilter())

def log_exception(e: Exception, context: str = ""):
    """Логирует исключение с контекстом."""
    logger.error(f"Ошибка в {context}: {str(e)}")
    logger.error("Traceback:")
    logger.error(traceback.format_exc())

class TokenLimitMonitor:
    """Мониторинг лимитов токенов"""
    def __init__(self):
        self.total_tokens = 0
        self.max_tokens = 1000  # Лимит на запрос
        self.total_requests = 0
        self.failed_requests = 0
        self.rate_limit_hits = 0
        
    def log_request(self, tokens: int, success: bool = True, rate_limited: bool = False):
        self.total_tokens += tokens
        self.total_requests += 1
        if not success:
            self.failed_requests += 1
        if rate_limited:
            self.rate_limit_hits += 1
            
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "rate_limit_hits": self.rate_limit_hits,
            "success_rate": (self.total_requests - self.failed_requests) / self.total_requests if self.total_requests > 0 else 0
        }

class ChatAnalyzerLLM:
    """Класс для анализа чата с использованием LLM."""
    
    # Список бесплатных моделей OpenRouter
    FREE_MODELS = [
        "meta-llama/llama-3.3-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "google/gemma-7b-it:free",
        "anthropic/claude-3-haiku:free",
        "meta-llama/llama-2-70b-chat:free",
        "google/gemma-2b-it:free",
        "microsoft/phi-2:free",
        "huggingfaceh4/zephyr-7b-beta:free"
    ]
    
    def __init__(self):
        """Инициализация сервиса LLM."""
        self.token_monitor = TokenLimitMonitor()
        self.current_model_index = 0
        
        # Получаем API ключ
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
            
        # Инициализируем LLM сервис
        self.llm_service = LLMService()
        
        # Настройки API
        self.api_base = "https://openrouter.ai/api/v1"
        self.model = self.FREE_MODELS[0]
        self.max_tokens = 1000
        self.temperature = 0.7
        self.max_retries = 3  # Увеличиваем количество попыток
        self.retry_delay = 1  # Начальная задержка в секундах
        
        # Инициализируем кеш
        self.cache = AnalysisCache()
        
        logger.info("Инициализирован сервис LLM с поддержкой кеширования")
        
        logger.info("Инициализирован сервис LLM")
        logger.info("=== Настройки лимитов ===")
        logger.info(f"Максимальное количество токенов на запрос: {self.max_tokens}")
        logger.info(f"Температура: {self.temperature}")
        logger.info(f"Максимальное количество попыток: {self.max_retries}")
        logger.info(f"Задержка между попытками: {self.retry_delay} сек")
        logger.info("=======================")
        self.ritual_keywords = [
            'ритуал', 'поток', 'практика', 'медитация', 'трансформация',
            'сессия', 'процесс', 'игра', 'ретрит', 'занятие', 'эфир', 'трансляция'
        ]
    
    def _get_next_model(self) -> Optional[str]:
        """Получает следующую доступную модель из списка."""
        if self.current_model_index < len(self.FREE_MODELS):
            model = self.FREE_MODELS[self.current_model_index]
            self.current_model_index += 1
            return model
        return None
        
    async def _analyze_with_prompt(self, messages: List[Dict[str, Any]], user_info: Dict[str, Any], prompt_type: str) -> Dict[str, Any]:
        """Анализирует сообщения с использованием заданного промпта.
        
        Args:
            messages: Список сообщений для анализа
            user_info: Информация о пользователе
            prompt_type: Тип промпта для анализа (например, 'psychological', 'behavioral' и т.д.)
            
        Returns:
            Словарь с результатами анализа
        """
        # Используем _analyze_user_messages, так как он более полный и структурированный
        result = await self._analyze_user_messages(messages)
        
        # Если нужен определенный тип анализа, извлекаем его из результата
        if prompt_type in ['psychological', 'behavioral', 'cognitive']:
            return result.get(f"{prompt_type}_analysis", {})
            
        return result
    
    async def _make_llm_request(self, prompt: str, model: str = None) -> Optional[str]:
        """
        Отправляет запрос к LLM и возвращает ответ.
        
        Args:
            prompt: Текст промпта для отправки в LLM
            model: Опциональное указание модели
            
        Returns:
            Ответ от LLM или None в случае ошибки
        """
        if not hasattr(self, 'llm_service') or not self.llm_service:
            logger.error("LLM сервис не инициализирован")
            return None
            
        if not hasattr(self.llm_service, 'generate_text'):
            logger.error("Метод generate_text не найден в LLM сервисе")
            return None
            
        logger.info(f"Отправка запроса к LLM. Длина промпта: {len(prompt)} символов")
        logger.debug(f"Используемая модель: {model or self.model}")
        
        for attempt in range(self.max_retries):
            try:
                # Используем метод generate_text из LLM сервиса
                response = await self.llm_service.generate_text(
                    prompt=prompt,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    model=model or self.model
                )
                
                if not response:
                    logger.error("Пустой ответ от LLM сервиса")
                    continue
                    
                logger.debug(f"Успешно получен ответ от LLM. Длина: {len(response)} символов")
                return response
                
            except Exception as e:
                wait_time = self.retry_delay * (attempt + 1)
                logger.warning(f"Попытка {attempt + 1}/{self.max_retries} не удалась: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    logger.info(f"Повторная попытка через {wait_time} сек...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Не удалось выполнить запрос после {self.max_retries} попыток")
                    return None
        
        return None
        
    def _get_default_analysis(self, username: str) -> Dict[str, Any]:
        """Возвращает структуру анализа по умолчанию.
        
        Args:
            username: Имя пользователя
            
        Returns:
            Словарь с структурой анализа по умолчанию
        """
        return {
            "name": username,
            "forensic_analysis": {
                "topics": [],
                "sentiment": "не определен",
                "patterns": [],
                "defense_mechanisms": [],
                "hidden_motives": []
            },
            "psychological_analysis": {
                "conflicts": [],
                "dependencies": [],
                "manipulation_patterns": [],
                "questions": []
            },
            "cognitive_analysis": {
                "distortions": [],
                "beliefs": [],
                "insights": []
            },
            "behavioral_analysis": {
                "patterns": [],
                "strategies": [],
                "difficulties": []
            },
            "complex_analysis": {
                "interconnections": [],
                "resistance_patterns": []
            },
            "transformation_advice": []
        }
        
    async def _analyze_user_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Анализирует сообщения одного пользователя с использованием LLM.
        
        Args:
            messages: Список сообщений пользователя
            
        Returns:
            Словарь с результатами анализа, включая психологический профиль
        """
        logger.info(f"Начало анализа {len(messages)} сообщений пользователя")
        if not messages:
            logger.warning("Нет сообщений для анализа")
            return self._get_default_analysis(username="Неизвестный участник")
            
        # Получаем информацию о пользователе из первого сообщения
        user_info = self._get_user_info(messages[0])
        username = user_info.get('name', 'Неизвестный участник')
        
        # Создаем прогресс-бар для обработки сообщений
        with tqdm(total=len(messages), desc=f"Анализ сообщений {username}", unit="сообщ.", ncols=100) as pbar:
            # Формируем текст сообщений
            processed_messages = []
            for msg in messages:
                text = self._extract_text(msg).strip()
                if text:
                    processed_messages.append(f"{msg.get('date', '')}: {text}")
                pbar.update(1)
                
            messages_text = "\n".join(processed_messages)
            
            if not messages_text.strip():
                logger.warning("Нет текста для анализа")
                return self._get_default_analysis(username=username)
            
            # Импортируем промпт
            from relove_bot.services.prompts import PSYCHOLOGICAL_ANALYSIS_PROMPT
            
            # Формируем полный промпт с именем пользователя в начале
            prompt = f"Пользователь: {username}\n\n{PSYCHOLOGICAL_ANALYSIS_PROMPT.format(messages=messages_text)}"
            
            # Отправляем запрос к LLM
            llm_response = await self._make_llm_request(prompt)
            
            if not llm_response:
                logger.error("Пустой ответ от LLM")
                return self._get_default_analysis(username=username)
            
            # Инициализируем response_text перед try-блоком
            response_text = llm_response.strip('```json').strip('```').strip()
            
            # Обрабатываем ответ
            try:
                # Логируем сырой ответ для отладки
                logger.debug(f"Сырой ответ от LLM: {response_text[:500]}..." if len(response_text) > 500 else f"Сырой ответ от LLM: {response_text}")
                
                # Парсим JSON с ответом
                analysis = json.loads(response_text)
                
                # Формируем структурированный результат
                return {
                    "name": username,
                    "forensic_analysis": {
                        "topics": analysis.get("forensic_analysis", {}).get("topics", []),
                        "sentiment": analysis.get("forensic_analysis", {}).get("sentiment", "не определен"),
                        "patterns": analysis.get("forensic_analysis", {}).get("patterns", []),
                        "defense_mechanisms": analysis.get("forensic_analysis", {}).get("defense_mechanisms", []),
                        "hidden_motives": analysis.get("forensic_analysis", {}).get("hidden_motives", [])
                    },
                    "psychological_analysis": {
                        "conflicts": analysis.get("psychological_analysis", {}).get("conflicts", []),
                        "dependencies": analysis.get("psychological_analysis", {}).get("dependencies", []),
                        "manipulation_patterns": analysis.get("psychological_analysis", {}).get("manipulation_patterns", []),
                        "questions": analysis.get("psychological_analysis", {}).get("questions", [])
                    },
                    "cognitive_analysis": {
                        "distortions": analysis.get("cognitive_analysis", {}).get("distortions", []),
                        "beliefs": analysis.get("cognitive_analysis", {}).get("beliefs", []),
                        "insights": analysis.get("cognitive_analysis", {}).get("insights", [])
                    },
                    "behavioral_analysis": {
                        "patterns": analysis.get("behavioral_analysis", {}).get("patterns", []),
                        "strategies": analysis.get("behavioral_analysis", {}).get("strategies", []),
                        "difficulties": analysis.get("behavioral_analysis", {}).get("difficulties", [])
                    },
                    "complex_analysis": {
                        "interconnections": analysis.get("complex_analysis", {}).get("interconnections", []),
                        "resistance_patterns": analysis.get("complex_analysis", {}).get("resistance_patterns", [])
                    },
                    "transformation_advice": analysis.get("transformation_advice", [])
                }
                
            except json.JSONDecodeError as je:
                logger.error(f"Ошибка декодирования JSON: {je}")
                # Пытаемся извлечь структурированную информацию из текста
                return self._extract_structured_info_from_text(response_text)
            
            except Exception as e:
                logger.error(f"Ошибка при анализе сообщений пользователя {username}: {str(e)}", exc_info=True)
                return self._get_default_analysis(username=username)


    def _add_to_result(self, result: Dict[str, Any], field_path: str, value: str) -> None:
        """
        Добавляет значение в указанное поле вложенной структуры результата.
        
        Args:
            result: Словарь с результатом
            field_path: Путь к полю в формате 'key1.key2.key3'
            value: Значение для добавления (может быть строкой или списком)
        """
        if not field_path or not value:
            return
            
        try:
            # Если значение - строка, убираем лишние пробелы и кавычки
            if isinstance(value, str):
                value = value.strip(' "\'')
                if not value:  # Пропускаем пустые значения
                    return
            
            # Разбиваем путь на компоненты
            parts = field_path.split('.')
            current = result
            
            # Проходим по всем частям пути, кроме последней
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Обрабатываем последнюю часть пути
            last_part = parts[-1]
            
            # Если поле еще не существует, создаем список
            if last_part not in current:
                current[last_part] = []
            
            # Если поле существует, но не является списком, преобразуем его в список
            if not isinstance(current[last_part], list):
                current[last_part] = [current[last_part]] if current[last_part] else []
            
            # Добавляем значение (или элементы, если value - список)
            if isinstance(value, list):
                for item in value:
                    if item and item not in current[last_part]:
                        current[last_part].append(item)
            elif value not in current[last_part]:  # Избегаем дубликатов
                current[last_part].append(value)
                
            logger.debug(f"Добавлено значение в {field_path}: {value}")
                
        except Exception as e:
            logger.warning(f"Ошибка при добавлении значения в результат: {e}")
            logger.debug(f"Поле: {field_path}, значение: {value}, тип: {type(value)}")
    
    def _extract_structured_info_from_text(self, text: str) -> Dict[str, Any]:
        """
        Пытается извлечь структурированную информацию из текстового ответа,
        когда не удалось распарсить JSON.
        
        Возвращает данные в формате, соответствующем PSYCHOLOGICAL_ANALYSIS_PROMPT.
        """
        # Получаем имя пользователя из первого сообщения, если оно есть
        username = None
        if hasattr(self, 'current_messages') and self.current_messages:
            user_info = self._get_user_info(self.current_messages[0])
            username = user_info.get('name')
        result = self._get_default_analysis(username=username)
        
        # Если текст пустой, возвращаем пустую структуру
        if not text or not text.strip():
            logger.warning("Пустой текст для извлечения структурированной информации")
            return result
            
        logger.info("Извлечение структурированной информации из текстового ответа LLM")
        logger.debug(f"Исходный текст для анализа: {text[:500]}...")
        
        try:
            # Преобразуем текст в нижний регистр для поиска
            text_lower = text.lower()
            
            # Словарь для поиска ключевых фраз и их соответствия полям результата
            field_mapping = {
                # Темы
                "темы": "forensic_analysis.topics",
                "основные темы": "forensic_analysis.topics",
                "ключевые темы": "forensic_analysis.topics",
                "топ темы": "forensic_analysis.topics",
                "главные темы": "forensic_analysis.topics",
                
                # Эмоциональный тон
                "эмоциональный тон": "forensic_analysis.sentiment",
                "настроение": "forensic_analysis.sentiment",
                "эмоции": "forensic_analysis.sentiment",
                "эмоциональная окраска": "forensic_analysis.sentiment",
                "эмоциональное состояние": "forensic_analysis.sentiment",
                
                # Паттерны
                "паттерны": "forensic_analysis.patterns",
                "шаблоны": "forensic_analysis.patterns",
                "повторяющиеся паттерны": "forensic_analysis.patterns",
                "поведенческие паттерны": "forensic_analysis.patterns",
                "коммуникативные паттерны": "forensic_analysis.patterns",
                
                # Защитные механизмы
                "защитные механизмы": "forensic_analysis.defense_mechanisms",
                "механизмы защиты": "forensic_analysis.defense_mechanisms",
                "защиты": "forensic_analysis.defense_mechanisms",
                "психологические защиты": "forensic_analysis.defense_mechanisms",
                "защитные стратегии": "forensic_analysis.defense_mechanisms",
                
                # Скрытые мотивы
                "скрытые мотивы": "forensic_analysis.hidden_motives",
                "мотивы": "forensic_analysis.hidden_motives",
                "неосознаваемые мотивы": "forensic_analysis.hidden_motives",
                "подсознательные мотивы": "forensic_analysis.hidden_motives",
                "неявные мотивы": "forensic_analysis.hidden_motives",
                
                # Конфликты
                "конфликты": "psychological_analysis.conflicts",
                "внутренние конфликты": "psychological_analysis.conflicts",
                "противоречия": "psychological_analysis.conflicts",
                "внутренние противоречия": "psychological_analysis.conflicts",
                "конфликтные зоны": "psychological_analysis.conflicts",
                
                # Зависимости
                "зависимости": "psychological_analysis.dependencies",
                "эмоциональные зависимости": "psychological_analysis.dependencies",
                "зависимое поведение": "psychological_analysis.dependencies",
                "психологические зависимости": "psychological_analysis.dependencies",
                "нездоровые привязанности": "psychological_analysis.dependencies",
                
                # Манипулятивные паттерны
                "манипулятивные паттерны": "psychological_analysis.manipulation_patterns",
                "манипуляции": "psychological_analysis.manipulation_patterns",
                "манипулятивное поведение": "psychological_analysis.manipulation_patterns",
                "манипулятивные техники": "psychological_analysis.manipulation_patterns",
                "способы манипуляции": "psychological_analysis.manipulation_patterns",
                
                # Вопросы
                "вопросы": "psychological_analysis.questions",
                "ключевые вопросы": "psychological_analysis.questions",
                "вопросы для размышления": "psychological_analysis.questions",
                "вопросы для исследования": "psychological_analysis.questions",
                "открытые вопросы": "psychological_analysis.questions",
                
                # Когнитивные искажения
                "когнитивные искажения": "cognitive_analysis.distortions",
                "искажения мышления": "cognitive_analysis.distortions",
                "ошибки мышления": "cognitive_analysis.distortions",
                "логические ошибки": "cognitive_analysis.distortions",
                "когнитивные ошибки": "cognitive_analysis.distortions",
                
                # Убеждения и установки
                "убеждения": "cognitive_analysis.beliefs",
                "установки": "cognitive_analysis.beliefs",
                "убеждения и установки": "cognitive_analysis.beliefs",
                "базовые убеждения": "cognitive_analysis.beliefs",
                "ограничивающие убеждения": "cognitive_analysis.beliefs",
                
                # Инсайты
                "инсайты": ["cognitive_analysis.insights", "insights"],
                "озарения": ["cognitive_analysis.insights", "insights"],
                "прозрения": ["cognitive_analysis.insights", "insights"],
                "понимания": ["cognitive_analysis.insights", "insights"],
                "ключевые инсайты": ["cognitive_analysis.insights", "insights"],
                
                # Поведенческие паттерны
                "поведенческие паттерны": "behavioral_analysis.patterns",
                "модели поведения": "behavioral_analysis.patterns",
                "привычки": "behavioral_analysis.patterns",
                "стереотипы поведения": "behavioral_analysis.patterns",
                "типичные реакции": "behavioral_analysis.patterns",
                
                # Стратегии
                "стратегии": "behavioral_analysis.strategies",
                "поведенческие стратегии": "behavioral_analysis.strategies",
                "способы взаимодействия": "behavioral_analysis.strategies",
                "подходы к решению": "behavioral_analysis.strategies",
                "стратегии совладания": "behavioral_analysis.strategies",
                
                # Трудности
                "трудности": "behavioral_analysis.difficulties",
                "проблемы": "behavioral_analysis.difficulties",
                "сложности": "behavioral_analysis.difficulties",
                "препятствия": "behavioral_analysis.difficulties",
                "вызовы": "behavioral_analysis.difficulties",
                
                # Взаимосвязи
                "взаимосвязи": "complex_analysis.interconnections",
                "связи": "complex_analysis.interconnections",
                "корреляции": "complex_analysis.interconnections",
                "взаимодействия": "complex_analysis.interconnections",
                "ассоциации": "complex_analysis.interconnections",
                
                # Паттерны сопротивления
                "паттерны сопротивления": "complex_analysis.resistance_patterns",
                "сопротивление": "complex_analysis.resistance_patterns",
                "сопротивление изменениям": "complex_analysis.resistance_patterns",
                "блоки": "complex_analysis.resistance_patterns",
                "психологические блоки": "complex_analysis.resistance_patterns",
                
                # Рекомендации
                "рекомендации": "transformation_advice",
                "советы": "transformation_advice",
                "рекомендации по трансформации": "transformation_advice",
                "советы по изменению": "transformation_advice",
                "рекомендации для развития": "transformation_advice"
            }
            
            # Разбиваем текст на строки и обрабатываем каждую
            lines = text.split('\n')
            current_field = None
            current_section = None
            in_list = False
            
            # Определяем, является ли текст структурированным (содержит заголовки)
            is_structured = any(':' in line and not line.startswith((' ', '\t', '-', '*', '•')) 
                              for line in lines if line.strip())
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    in_list = False
                    continue
                    
                # Пропускаем строки, состоящие только из разделителей
                if all(c in '-=' for c in line.strip()):
                    in_list = False
                    continue
                    
                line_lower = line.lower()
                found_field = False
                
                # Обработка маркированных списков
                is_list_item = any(line_lower.lstrip().startswith(marker) 
                                 for marker in ('-', '*', '•', '1.', '2.', '3.', '•', '—'))
                
                # Если это элемент списка и есть активное поле
                if is_list_item and current_field and current_field in field_mapping:
                    # Удаляем маркер списка и лишние пробелы
                    item = line.lstrip('*-• ').lstrip('0123456789.').strip()
                    if item:  # Добавляем только непустые элементы
                        field_paths = field_mapping[current_field]
                        if isinstance(field_paths, str):
                            field_paths = [field_paths]
                        for field_path in field_paths:
                            self._add_to_result(result, field_path, item)
                    in_list = True
                    continue
                
                # Сбрасываем флаг списка, если нашли не элемент списка
                if not is_list_item:
                    in_list = False
                
                # Ищем известные заголовки секций с двоеточием
                if ':' in line and not line.startswith((' ', '\t', '-', '*', '•')):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key_part, value_part = parts
                        key = key_part.strip().lower()
                        value = value_part.strip()
                        
                        # Проверяем, является ли ключ известным полем
                        if key in field_mapping:
                            field_path = field_mapping[key]
                            if isinstance(field_path, list):
                                field_path = field_path[0]
                            
                            # Если значение не пустое, добавляем его
                            if value:
                                self._add_to_result(result, field_path, value)
                            
                            # Запоминаем текущее поле для обработки следующих строк
                            current_field = key
                            found_field = True
                            continue
                
                # Если не нашли структурированное поле, ищем по ключевым словам
                if not found_field:
                    for keyword, field_path in field_mapping.items():
                        # Проверяем, начинается ли строка с ключевого слова
                        if (line_lower.startswith(keyword) or 
                            f' {keyword}:' in f' {line_lower}' or 
                            f' {keyword} ' in f' {line_lower} '):
                            
                            # Извлекаем значение после ключевого слова
                            if ':' in line:
                                value = line.split(':', 1)[1].strip()
                            else:
                                value = line[line_lower.find(keyword) + len(keyword):].strip(' :;-.,')
                            
                            if value:  # Если есть значение после ключевого слова
                                if isinstance(field_path, list):
                                    field_path = field_path[0]
                                self._add_to_result(result, field_path, value)
                                current_field = keyword
                                found_field = True
                                break
                
                # Если нашли новую секцию, запоминаем её
                if not found_field and (line.endswith(':') or 
                                      any(line_lower.startswith(sec) 
                                          for sec in ['тема:', 'эмоци', 'инсайт', 'рекомендац', 'вопрос', 'проблем'])):
                    section_name = line_lower.rstrip(':').strip()
                    current_section = section_name
                    
                    # Сопоставляем с известными полями
                    for keyword, field_path in field_mapping.items():
                        if keyword in section_name:
                            current_field = keyword
                            found_field = True
                            break
                
                # Обработка многострочных значений
                if not found_field and current_field and current_field in field_mapping and line.strip():
                    field_path = field_mapping[current_field]
                    if isinstance(field_path, list):
                        field_path = field_path[0]
                    
                    # Проверяем, не является ли строка началом нового блока
                    is_new_block = any(line_lower.startswith(keyword) for keyword in field_mapping.keys())
                    
                    if not is_new_block and not is_list_item and not in_list:
                        self._add_to_result(result, field_path, line.strip())
                
                # Если это не структурированный текст и не нашли поле, пробуем угадать по контексту
                if not is_structured and not found_field and not current_field:
                    for keyword, field_path in field_mapping.items():
                        if keyword in line_lower:
                            if isinstance(field_path, list):
                                field_path = field_path[0]
                            self._add_to_result(result, field_path, line)
                            current_field = keyword
                            break
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении структурированной информации: {e}")
            logger.debug(f"Текст, вызвавший ошибку: {text}")
            return result
    
    def _get_default_analysis(self, username: str) -> Dict[str, Any]:
        """Возвращает структуру анализа по умолчанию, соответствующую PSYCHOLOGICAL_ANALYSIS_PROMPT.
        
        Args:
            username: Имя пользователя. Обязательный параметр.
            
        Returns:
            Словарь с структурой анализа по умолчанию.
            
        Raises:
            ValueError: Если имя пользователя не указано.
        """
        if not username:
            raise ValueError("Имя пользователя обязательно должно быть указано")
        return {
            "name": username,
            "forensic_analysis": {
                "topics": [],
                "sentiment": "не определен",
                "patterns": [],
                "defense_mechanisms": [],
                "hidden_motives": []
            },
            "psychological_analysis": {
                "conflicts": [],
                "dependencies": [],
                "manipulation_patterns": [],
                "questions": [],
                "emotional_state": "не определено",
                "behavioral_patterns": [],
                "emotions": []
            },
            "cognitive_analysis": {
                "distortions": [],
                "beliefs": [],
                "insights": []
            },
            "behavioral_analysis": {
                "patterns": [],
                "strategies": [],
                "difficulties": [],
                "coping_mechanisms": []
            },
            "complex_analysis": {
                "interconnections": [],
                "resistance_patterns": [],
                "systemic_patterns": []
            },
            "transformation_advice": [],
            "key_insights": [],
            "recommendations": [],
            "themes": []
        }

    def _group_by_user(self, messages: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Группирует сообщения по пользователям, используя from_id в качестве ключа.
        
        Args:
            messages: Список сообщений для группировки
            
        Returns:
            Словарь, где ключ - ID пользователя, значение - список его сообщений
        """
        user_messages = defaultdict(list)
        
        for msg in messages:
            # Пытаемся получить ID пользователя из различных полей
            user_id = None
            
            # 1. Пробуем получить из from_id
            if 'from_id' in msg:
                user_id = str(msg['from_id'])
            # 2. Пробуем получить из from (если это словарь с id)
            elif 'from' in msg and isinstance(msg['from'], dict) and 'id' in msg['from']:
                user_id = str(msg['from']['id'])
            # 3. Пробуем получить из user_id
            elif 'user_id' in msg:
                user_id = str(msg['user_id'])
            # 4. Если from - это строка, используем её как ID
            elif 'from' in msg and isinstance(msg['from'], str):
                user_id = msg['from']
            
            # Если ID найден, добавляем сообщение в соответствующую группу
            if user_id:
                # Сохраняем оригинальное имя пользователя в каждом сообщении
                if 'from' in msg and isinstance(msg['from'], dict):
                    first_name = msg['from'].get('first_name', '').strip()
                    last_name = msg['from'].get('last_name', '').strip()
                    name = ' '.join(part for part in [first_name, last_name] if part)
                    if name:
                        msg['original_name'] = name
                
                user_messages[user_id].append(msg)
        
        return dict(user_messages)

    def _save_report(self, report: Dict[str, Any], path: Union[str, Path]) -> bool:
        """Сохраняет отчет в файл.
        
        Args:
            report: Словарь с данными отчета
            path: Путь для сохранения отчета
            
        Returns:
            bool: True, если сохранение прошло успешно, иначе False
        """
        try:
            # Преобразуем путь в объект Path, если это строка
            path = Path(path) if isinstance(path, str) else path
            
            # Создаем директорию, если она не существует
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем отчет в файл
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
                
            logger.info(f"Отчет успешно сохранен: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении отчета в {path}: {str(e)}")
            return False

    def _extract_text(self, msg: Dict[str, Any]) -> str:
        """Извлекает текст из сообщения, обрабатывая различные форматы.
        
        Поддерживает:
        - Простой текст
        - Текст с форматированием (вложенные словари с type и text)
        - Списки текстовых фрагментов
        """
        def process_text_item(item):
            """Обрабатывает отдельный элемент текста, который может быть строкой или словарем."""
            if isinstance(item, str):
                return item
            elif isinstance(item, dict):
                return item.get('text', '')
            return ''
        
        # Получаем текст сообщения
        text_content = msg.get('text', msg.get('message', ''))
            
        # Обрабатываем разные форматы текста
        if isinstance(text_content, list):
            # Если текст представлен списком (например, с форматированием)
            parts = []
            for item in text_content:
                if isinstance(item, dict) and 'text' in item:
                    parts.append(process_text_item(item))
                else:
                    parts.append(str(item))
            text = ' '.join(parts)
        elif isinstance(text_content, dict):
            # Если текст в виде словаря
            text = process_text_item(text_content)
        else:
            # Простой текст
            text = str(text_content)
                
        # Убираем лишние пробелы и переносы строк
        return ' '.join(text.split())

    def _get_user_info(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Извлекает информацию о пользователе из сообщения.
        
        Возвращает словарь с ключами:
        - id: ID пользователя (из from_id или user_id)
        - name: Полное имя пользователя (из from или name)
        - username: Имя пользователя (если есть)
        """
        try:
            # Инициализируем переменные
            user_id = ''
            name = ''
            username = ''
            
            # 1. Пробуем получить ID пользователя
            if 'from_id' in message:
                user_id = str(message['from_id'])
            elif 'from' in message and isinstance(message['from'], dict) and 'id' in message['from']:
                user_id = str(message['from']['id'])
            elif 'user_id' in message:
                user_id = str(message['user_id'])
            
            # 2. Получаем имя пользователя
            if 'from' in message:
                from_field = message['from']
                if isinstance(from_field, dict):
                    # Если from - словарь, берем имя как есть из полей first_name и last_name
                    first_name = from_field.get('first_name', '').strip()
                    last_name = from_field.get('last_name', '').strip()
                    name = ' '.join(part for part in [first_name, last_name] if part)
                    username = from_field.get('username', '').strip()
                elif isinstance(from_field, str):
                    # Если from - строка, используем её как имя
                    name = from_field.strip()
            
            # 3. Если имя не нашли, пробуем другие поля
            if not name:
                name = (message.get('name') or message.get('full_name') or '').strip()
            
            # 4. Если имя так и не нашли, используем имя пользователя или ID
            if not name:
                if username:
                    name = username
                elif user_id:
                    name = f"Участник {user_id}"
                else:
                    name = "Неизвестный участник"
            
            return {
                'id': user_id,
                'name': name,
                'username': username
            }
                
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе: {e}")
            return {
                'id': '',
                'name': 'Участник',
                'username': ''
            }

            # Инициализируем переменные
            user_id = ''
            name_parts = []
            username = ''
            
            # Пытаемся получить информацию из поля from
            if 'from' in message:
                from_field = message['from']
                if isinstance(from_field, dict):
                    # Собираем имя из first_name и last_name, если они есть
                    first_name = from_field.get('first_name', '').strip()
                    last_name = from_field.get('last_name', '').strip()
                    
                    if first_name or last_name:
                        name_parts = [part for part in [first_name, last_name] if part]
                    
                    user_id = str(from_field.get('id', ''))
                    username = from_field.get('username', '').strip()
                    
                    # Если есть username, но нет имени, используем username как имя
                name = ' '.join(name_parts)
            
            # Удаляем лишние пробелы и проверяем, что имя не пустое
            name = name.strip()
            if not name:
                name = f"Участник {user_id[-4:]}" if user_id else "Участник"
            
            return {
                'id': user_id,
                'name': name,
                'username': username
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе: {e}")
            return {
                'id': '',
                'name': 'Участник',
                'username': ''
            }

    async def analyze_chat(self, data: Dict[str, Any], use_cache: bool = True) -> Dict[str, Any]:
        """Анализирует чат с использованием LLM для определения психологических профилей участников.
        
        Args:
            data: Данные чата для анализа
            use_cache: Использовать ли кеширование результатов (по умолчанию True)
            
        Returns:
            Dict: Словарь с результатами анализа, включая путь к сохраненному отчету.
        """
        logger.info("=== Начало анализа чата ===")
        logger.info(f"Использование кеша: {'включено' if use_cache else 'отключено'}")
            
        if not data:
            error_msg = "Нет данных для анализа: data пуст"
            logger.error(error_msg)
            return {"error": error_msg}
                
        if 'messages' not in data:
            error_msg = "Отсутствует ключ 'messages' в данных"
            logger.error(error_msg)
            return {"error": error_msg}
                
        try:
            messages = data['messages']
            if not messages:
                error_msg = "Список сообщений пуст"
                logger.error(error_msg)
                return {"error": error_msg}
                
            # Группируем сообщения по пользователям
            user_messages = self._group_by_user(messages)
            total_users = len(user_messages)
            logger.info(f"Найдено уникальных пользователей: {total_users}")
                
            if not user_messages:
                error_msg = "Не удалось сгруппировать сообщения по пользователям"
                logger.error(error_msg)
                return {"error": error_msg}
            
            # Создаем отчет
            report = {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "total_users": total_users,
                    "analyzed_users": 0,
                    "cached_users": 0,
                    "failed_users": 0,
                    "use_cache": use_cache
                },
                "results": {}
            }
            
            # Создаем папку для отчета
            try:
                today = datetime.now().strftime('%Y-%m-%d')
                report_dir = Path('reports') / today
                
                # Создаем полный путь, если его нет
                report_dir.mkdir(parents=True, exist_ok=True)
                
                # Формируем имя файла отчета
                safe_flow_name = "".join(c if c.isalnum() or c in ' _-' else '_' 
                                       for c in data.get('name', 'Неизвестный чат'))
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                report_filename = f"analysis_{safe_flow_name[:50]}_{timestamp}.json"
                report_path = report_dir / report_filename
                
                # Проверяем, что путь доступен для записи
                if not os.access(report_dir, os.W_OK):
                    error_msg = f"Нет прав на запись в директорию: {report_dir}"
                    logger.error(error_msg)
                    return {"error": error_msg}
                    
            except Exception as e:
                error_msg = f"Ошибка при создании директории для отчета: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {"error": error_msg}
            
            # Анализируем каждого пользователя с прогресс-баром (верхний)
            with tqdm(
                total=total_users,
                desc="Анализ пользователей",
                unit="пользователь",
                dynamic_ncols=True,
                position=0,
                leave=False
            ) as pbar:
                # Общий прогресс (нижний)
                with tqdm(
                    total=total_users * 2,  # Удваиваем для двух стадий: анализ + сохранение
                    desc="Общий прогресс",
                    unit="шаг",
                    dynamic_ncols=True,
                    position=1,
                    leave=True,
                    bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]'
                ) as main_pbar:
                    for user_id, msgs in user_messages.items():
                        try:
                            if not msgs or not isinstance(msgs, list):
                                logger.warning(f"Нет сообщений для пользователя {user_id}")
                                report["metadata"]["failed_users"] += 1
                                main_pbar.update(1)  # Обновляем общий прогресс
                                continue
                                
                            try:
                                user_info = self._get_user_info(msgs[0])
                                username = user_info.get('name', str(user_id))
                                pbar.set_description(f"Анализ: {username[:20]}")
                            except Exception as e:
                                logger.error(f"Ошибка при получении информации о пользователе {user_id}: {e}")
                                report["metadata"]["failed_users"] += 1
                                main_pbar.update(1)  # Обновляем общий прогресс
                                continue
                            
                            # Пытаемся загрузить из кеша
                            analysis = None
                            if use_cache:
                                cached_result = self.cache.get_cached_result(user_id, msgs)
                                if cached_result:
                                    analysis = cached_result['data']
                                    report["metadata"]["cached_users"] += 1
                                    logger.info(f"Использован кеш для пользователя {username}")
                            
                            # Если не нашли в кеше, анализируем
                            if not analysis:
                                logger.info(f"Анализ пользователя {username}")
                                analysis = await self._analyze_with_prompt(msgs, user_info, "event")
                                if isinstance(analysis, dict) and not analysis.get('error'):
                                    # Сохраняем в кеш
                                    cache_path = self.cache.save_result(user_id, msgs, analysis)
                                    if cache_path:
                                        logger.debug(f"Результат сохранен в кеш: {cache_path}")
                            
                            # Добавляем в результаты
                            if isinstance(analysis, dict) and not analysis.get('error'):
                                report["results"][user_id] = analysis
                                report["metadata"]["analyzed_users"] += 1
                            
                            # Сохраняем промежуточные результаты
                            self._save_report(report, report_path)
                            
                        except Exception as e:
                            username = user_info.get('name', str(user_id)) if 'user_info' in locals() else str(user_id)
                            error_msg = f"Ошибка при анализе пользователя {username}: {str(e)}"
                            logger.error(error_msg, exc_info=True)
                            report["metadata"]["failed_users"] += 1
                        finally:
                            pbar.update(1)  # Обновляем прогресс анализа пользователей
                            main_pbar.update(1)  # Обновляем общий прогресс
            
            # Завершаем отчет
            report["metadata"]["completed_at"] = datetime.now().isoformat()
            
            if not report["results"]:
                error_msg = "Не удалось проанализировать ни одного пользователя"
                logger.error(error_msg)
                return {"error": error_msg}
            
            # Сохраняем финальный отчет
            self._save_report(report, report_path)
            
            # Генерируем текстовый отчет
            flow_name = f"{data.get('name', 'Неизвестный чат')}"
            if 'date' in data:
                try:
                    chat_date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                    flow_name += f" от {chat_date.strftime('%d.%m.%Y')}"
                except (ValueError, TypeError):
                    pass
                    
            text_report = self._generate_text_report(report["results"], flow_name)
            text_report_path = report_path.with_suffix('.txt')
            
            try:
                with open(text_report_path, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(text_report)
                
                logger.info(f"Отчет успешно сохранен: {report_path}")
                logger.info(f"Текстовый отчет: {text_report_path}")
                
                return {
                    "success": True,
                    "report_path": str(report_path),
                    "text_report_path": str(text_report_path),
                    "stats": report["metadata"]
                }
                
            except Exception as e:
                error_msg = f"Ошибка при сохранении текстового отчета: {str(e)}"
                logger.error(error_msg)
                return {
                    "error": error_msg,
                    "report_path": str(report_path) if 'report_path' in locals() else None
                }
                
        except Exception as e:
            error_msg = f"Критическая ошибка при анализе чата: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {"error": error_msg}

    def _get_section_content(self, data: Dict, section: str, field: str, default: Any = 'не выявлено') -> str:
        """Получает содержимое секции отчета с обработкой ошибок."""
        try:
            section_data = data.get(section, {})
            if not section_data:
                return str(default)
                
            value = section_data.get(field, default)
            if isinstance(value, (list, tuple)):
                return ', '.join(str(v) for v in value) if value else str(default)
            return str(value) if value is not None else str(default)
        except Exception as e:
            logger.error(f"Ошибка при получении данных {section}.{field}: {e}")
            return str(default)

    def _generate_text_report(self, results: Dict[str, Any], flow_name: str = "") -> str:
        """Генерирует структурированный отчет в формате Markdown.
        
        Args:
            results: Результаты анализа чата
            flow_name: Название потока/чата
            
        Returns:
            str: Текст отчета в формате Markdown
        """
        try:
            timestamp = datetime.now().strftime('%d.%m.%Y %H:%M')
            
            # Создаем заголовок отчета
            report_lines = [
                "# 📊 Анализ чата reLove\n",
                f"## 📌 Основная информация",
                f"- **Поток:** {flow_name}",
                f"- **Дата отчета:** {timestamp}",
                f"- **Всего участников:** {len(results)}\n"
            ]
            
            logger.info(f"Начало генерации отчета для {len(results)} участников")
            
            # Инициализируем словарь для сбора общей статистики
            total_analysis = {
                'forensic': set(),
                'psychological': set(),
                'cognitive': set(),
                'emotional': set(),
                'behavioral': set(),
                'transformation': set()  # Добавляем категорию для рекомендаций по трансформации
            }
            
            # Собираем информацию о пользователях
            user_info_map = {}
            for user_id, profile in results.items():
                # Получаем оригинальное имя из первого сообщения пользователя, если оно есть
                first_message = next((msg for msg in profile.get('messages', []) if 'original_name' in msg), None)
                
                if first_message and 'original_name' in first_message:
                    # Используем оригинальное имя из сообщения
                    username = first_message['original_name']
                else:
                    # Используем имя из профиля, если оно есть
                    username = profile.get('name', '').strip()
                    
                    # Если имя пустое или неизвестное, используем ID
                    if not username or username.lower() in ['неизвестный', 'unknown']:
                        username = f'Участник {user_id}'
                
                # Сохраняем имя пользователя для отображения
                user_info_map[user_id] = username
            
            # Обрабатываем каждого пользователя отдельно
            for user_id, profile in results.items():
                # Получаем имя пользователя из нашей карты
                username = user_info_map.get(user_id, f'Участник {user_id}')
                
                # Добавляем заголовок пользователя
                report_lines.append(f"\n{'='*50}")
                report_lines.append(f"## 👤 {username}")
                report_lines.append(f"*ID: {user_id}*")
                report_lines.append("")
                
                # 1. ФОРЕНЗИЧЕСКИЙ АНАЛИЗ
                forensic = profile.get('forensic_analysis', {})
                if forensic and any(forensic.values()):
                    report_lines.append("### 🔍 ФОРЕНЗИЧЕСКИЙ АНАЛИЗ\n")
                    
                    # Языковые паттерны и стиль общения
                    patterns = forensic.get('patterns', [])
                    if patterns and isinstance(patterns, list):
                        report_lines.append("**🗣️ Языковые паттерны и стиль общения:**\n")
                        report_lines.extend([f"- {p}" for p in patterns if isinstance(p, str)])
                        report_lines.append("")
                        total_analysis['forensic'].update(patterns)
                    
                    # Защитные механизмы
                    defense_mechanisms = forensic.get('defense_mechanisms', [])
                    if defense_mechanisms and isinstance(defense_mechanisms, list):
                        report_lines.append("**🛡️ Защитные механизмы:**\n")
                        report_lines.extend([f"- {d}" for d in defense_mechanisms if isinstance(d, str)])
                        report_lines.append("")
                        total_analysis['forensic'].update(defense_mechanisms)
                    
                    # Скрытые мотивы
                    hidden_motives = forensic.get('hidden_motives', [])
                    if hidden_motives and isinstance(hidden_motives, list):
                        report_lines.append("**🎯 Скрытые мотивы и желания:**\n")
                        report_lines.extend([f"- {m}" for m in hidden_motives if isinstance(m, str)])
                        report_lines.append("")
                        total_analysis['forensic'].update(hidden_motives)
                
                # 2. ПСИХОАНАЛИТИЧЕСКИЙ АНАЛИЗ
                psych = profile.get('psychological_analysis', {})
                if psych and any(psych.values()):
                    report_lines.append("### 🧠 ПСИХОАНАЛИТИЧЕСКИЙ АНАЛИЗ\n")
                    
                    # Внутренние конфликты
                    conflicts = psych.get('conflicts', [])
                    if conflicts and isinstance(conflicts, list):
                        report_lines.append("**⚔️ Внутренние конфликты:**\n")
                        report_lines.extend([f"- {c}" for c in conflicts if isinstance(c, str)])
                        report_lines.append("")
                        total_analysis['psychological'].update(conflicts)
                    
                    # Зависимости
                    dependencies = psych.get('dependencies', [])
                    if dependencies and isinstance(dependencies, list):
                        report_lines.append("**🔗 Психологические зависимости:**\n")
                        report_lines.extend([f"- {d}" for d in dependencies if isinstance(d, str)])
                        report_lines.append("")
                        total_analysis['psychological'].update(dependencies)
                    
                    # Манипулятивные стратегии
                    manipulation_patterns = psych.get('manipulation_patterns', [])
                    if manipulation_patterns and isinstance(manipulation_patterns, list):
                        report_lines.append("**🎭 Манипулятивные стратегии:**\n")
                        report_lines.extend([f"- {m}" for m in manipulation_patterns if isinstance(m, str)])
                        report_lines.append("")
                        total_analysis['psychological'].update(manipulation_patterns)
                
                # 3. КОГНИТИВНЫЙ АНАЛИЗ
                cognitive = profile.get('cognitive_analysis', {})
                if cognitive and any(cognitive.values()):
                    report_lines.append("### 🧩 КОГНИТИВНЫЙ АНАЛИЗ\n")
                    
                    # Когнитивные искажения
                    distortions = cognitive.get('distortions', [])
                    if distortions and isinstance(distortions, list):
                        report_lines.append("**🔄 Когнитивные искажения:**\n")
                        report_lines.extend([f"- {d}" for d in distortions if isinstance(d, str)])
                        report_lines.append("")
                        total_analysis['cognitive'].update(distortions)
                    
                    # Убеждения и установки
                    beliefs = cognitive.get('beliefs', [])
                    if beliefs and isinstance(beliefs, list):
                        report_lines.append("**💭 Убеждения и установки:**\n")
                        report_lines.extend([f"- {b}" for b in beliefs if isinstance(b, str)])
                        report_lines.append("")
                        total_analysis['cognitive'].update(beliefs)
                
                # 4. ЭМОЦИОНАЛЬНЫЙ АНАЛИЗ
                emotional = profile.get('emotional_analysis', {})
                if emotional and any(emotional.values()):
                    report_lines.append("### ❤️ ЭМОЦИОНАЛЬНЫЙ АНАЛИЗ\n")
                    
                    # Базовые эмоции
                    emotions = emotional.get('emotions', [])
                    if emotions and isinstance(emotions, list):
                        report_lines.append("**😊 Базовые эмоции:**\n")
                        report_lines.extend([f"- {e}" for e in emotions if isinstance(e, str)])
                        report_lines.append("")
                        total_analysis['emotional'].update(emotions)
                    
                    # Эмоциональные триггеры
                    triggers = emotional.get('triggers', [])
                    if triggers and isinstance(triggers, list):
                        report_lines.append("**⚡ Эмоциональные триггеры:**\n")
                        report_lines.extend([f"- {t}" for t in triggers if isinstance(t, str)])
                        report_lines.append("")
                        total_analysis['emotional'].update(triggers)
                    
                    # Страхи и тревоги
                    fears = emotional.get('fears', [])
                    if fears and isinstance(fears, list):
                        report_lines.append("😨 **Страхи и тревоги:**\n")
                        report_lines.extend([f"- {f}" for f in fears if isinstance(f, str)])
                        report_lines.append("")
                        total_analysis['emotional'].update(fears)
                
                # 5. ПОВЕДЕНЧЕСКИЙ АНАЛИЗ
                behavioral = profile.get('behavioral_analysis', {})
                if behavioral and any(behavioral.values()):
                    report_lines.append("### 🚶 ПОВЕДЕНЧЕСКИЙ АНАЛИЗ\n")
                    
                    # Паттерны поведения
                    patterns = behavioral.get('patterns', [])
                    if patterns and isinstance(patterns, list):
                        report_lines.append("**🔄 Паттерны поведения:**\n")
                        report_lines.extend([f"- {p}" for p in patterns if isinstance(p, str)])
                        report_lines.append("")
                        total_analysis['behavioral'].update(patterns)
                    
                    # Привычки
                    habits = behavioral.get('habits', [])
                    if habits and isinstance(habits, list):
                        report_lines.append("**📝 Привычки и рутины:**\n")
                        report_lines.extend([f"- {h}" for h in habits if isinstance(h, str)])
                        report_lines.append("")
                        total_analysis['behavioral'].update(habits)
                    
                    # Реакции на стресс
                    stress_responses = behavioral.get('stress_responses', [])
                    if stress_responses and isinstance(stress_responses, list):
                        report_lines.append("💢 **Реакции на стресс:**\n")
                        report_lines.extend([f"- {s}" for s in stress_responses if isinstance(s, str)])
                        report_lines.append("")
                        total_analysis['behavioral'].update(stress_responses)
                
                # 6. ИНСАЙТЫ И ВОЗМОЖНОСТИ ДЛЯ РОСТА
                transformation_advice = profile.get('transformation_advice', [])
                if transformation_advice and isinstance(transformation_advice, list) and len(transformation_advice) > 0:
                    report_lines.append("### 💫 ИНСАЙТЫ И ВОЗМОЖНОСТИ ДЛЯ РОСТА\n")
                    
                    # Форматируем каждый пункт, добавляя эмпатию и поддержку
                    valid_advice = []
                    for advice in transformation_advice:
                        if not isinstance(advice, str) or not advice.strip():
                            continue
                            
                        # Добавляем мягкость и поддержку в формулировки
                        advice = advice.strip()
                        if not advice.endswith(('.', '!', '?')):
                            advice += '.'
                            
                        # Заменяем резкие формулировки на более мягкие
                        advice = advice.replace('нужно', 'можно попробовать')
                        advice = advice.replace('должны', 'стоит')
                        advice = advice.replace('обязательно', 'важно')
                        advice = advice.replace('необходимо', 'полезно')
                        
                        valid_advice.append(advice)
                    
                    if valid_advice:
                        # Добавляем вводное предложение с поддержкой
                        report_lines.append("Вот что может помочь на пути к гармонии и счастью:\n")
                        
                        # Добавляем отформатированные рекомендации
                        for advice in valid_advice:
                            # Делаем первую букву строчной для плавности чтения
                            if advice and len(advice) > 0:
                                advice = advice[0].lower() + advice[1:]
                            report_lines.append(f"- {advice}")
                        
                        # Добавляем завершающую поддержку
                        report_lines.append("\nПомни, что каждый шаг к себе — это уже достижение. 💖\n")
                        
                        # Сохраняем оригинальные рекомендации для статистики
                        total_analysis['transformation'].update(valid_advice)
            
            # Удаляем общую статистику по фазам, оставляем только индивидуальные отчёты
            
            # Добавляем заключение
            report_lines.extend([
                "## 🏁 Заключение",
                "",
                f"Анализ завершен успешно. Обработано {len(results)} участников.",
                "",
                "*Отчет сгенерирован автоматически на основе анализа переписки в чате.*",
                ""
            ])
            
            # Объединяем все строки отчета в один текст
            text_report = "\n".join(report_lines)
            
            return text_report
            
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            return ""
            
    def _extract_structured_info_from_text(self, text: str) -> Dict:
        """Извлекает структурированную информацию из текста."""
        result = {
            'forensic_analysis': {},
            'psychological_analysis': {},
            'cognitive_analysis': {},
            'emotional_analysis': {},
            'behavioral_analysis': {}
        }
        
        if not text or not isinstance(text, str):
            logger.warning("Получен пустой или некорректный текст для анализа")
            return result
            
        try:
            # Приводим текст к нижнему регистру для удобства поиска
            text_lower = text.lower()
            
            # Словарь для маппинга ключевых слов на пути к полям
            field_mapping = {
                # Поля форензического анализа
                'языковые паттерны': 'forensic_analysis.patterns',
                'стиль общения': 'forensic_analysis.patterns',
                'защитные механизмы': 'forensic_analysis.defense_mechanisms',
                'скрытые мотивы': 'forensic_analysis.hidden_motives',
                'скрытые желания': 'forensic_analysis.hidden_motives',
                
                # Поля психологического анализа
                'внутренние конфликты': 'psychological_analysis.conflicts',
                'психологические зависимости': 'psychological_analysis.dependencies',
                'манипулятивные стратегии': 'psychological_analysis.manipulation_patterns',
                'манипулятивное поведение': 'psychological_analysis.manipulation_patterns',
                'манипулятивные техники': 'psychological_analysis.manipulation_patterns',
                'способы манипуляции': 'psychological_analysis.manipulation_patterns',
                'вопросы': 'psychological_analysis.questions',
                'ключевые вопросы': 'psychological_analysis.questions',
                'вопросы для размышления': 'psychological_analysis.questions',
                
                # Поля когнитивного анализа
                'когнитивные искажения': 'cognitive_analysis.distortions',
                'убеждения': 'cognitive_analysis.beliefs',
                'установки': 'cognitive_analysis.beliefs',
                
                # Поля эмоционального анализа
                'эмоции': 'emotional_analysis.emotions',
                'базовые эмоции': 'emotional_analysis.emotions',
                'эмоциональные триггеры': 'emotional_analysis.triggers',
                'страхи': 'emotional_analysis.fears',
                'тревоги': 'emotional_analysis.fears',
                
                # Поля поведенческого анализа
                'паттерны поведения': 'behavioral_analysis.patterns',
                'привычки': 'behavioral_analysis.habits',
                'рутины': 'behavioral_analysis.habits',
                'реакции на стресс': 'behavioral_analysis.stress_responses'
            }
            
            # Разбиваем текст на строки и обрабатываем каждую
            lines = text.split('\n')
            current_field = None
            in_list = False
            is_structured = True  # Флаг для структурированного текста
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                line_lower = line.lower()
                found_field = False
                
                # Проверяем, является ли строка элементом списка
                is_list_item = line.startswith(('- ', '* ', '• '))
                
                # Если находимся внутри списка, продолжаем добавлять к текущему полю
                if in_list and is_list_item:
                    item = line.lstrip('*-• ').lstrip('0123456789.').strip()
                    if item and current_field in field_mapping:  # Добавляем только непустые элементы
                        field_path = field_mapping[current_field]
                        if isinstance(field_path, list):
                            field_path = field_path[0]
                        self._add_to_result(result, field_path, item)
                    in_list = True
                    continue
                
                # Сбрасываем флаг списка, если нашли не элемент списка
                if not is_list_item:
                    in_list = False
                
                # Ищем известные заголовки секций с двоеточием
                if ':' in line and not line.startswith((' ', '\t', '-', '*', '•')):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key_part, value_part = parts
                        key = key_part.strip().lower()
                        value = value_part.strip()
                        
                        # Проверяем, является ли ключ известным полем
                        if key in field_mapping:
                            field_path = field_mapping[key]
                            if isinstance(field_path, list):
                                field_path = field_path[0]
                            
                            # Если значение не пустое, добавляем его
                            if value:
                                self._add_to_result(result, field_path, value)
                            
                            # Запоминаем текущее поле для обработки следующих строк
                            current_field = key
                            found_field = True
                            continue
                
                # Если не нашли структурированное поле, ищем по ключевым словам
                if not found_field:
                    for keyword, field_path in field_mapping.items():
                        # Проверяем, начинается ли строка с ключевого слова
                        if (line_lower.startswith(keyword) or 
                            f' {keyword}:' in f' {line_lower}' or 
                            f' {keyword} ' in f' {line_lower} '):
                            
                            # Извлекаем значение после ключевого слова
                            if ':' in line:
                                value = line.split(':', 1)[1].strip()
                            else:
                                value = line[line_lower.find(keyword) + len(keyword):].strip(' :;-.,')
                            
                            if value:  # Если есть значение после ключевого слова
                                if isinstance(field_path, list):
                                    field_path = field_path[0]
                                self._add_to_result(result, field_path, value)
                                current_field = keyword
                                found_field = True
                                break
                
                # Если нашли новую секцию, запоминаем её
                if not found_field and (line.endswith(':') or 
                                      any(line_lower.startswith(sec) 
                                          for sec in ['тема:', 'эмоци', 'инсайт', 'рекомендац', 'вопрос', 'проблем'])):
                    section_name = line_lower.rstrip(':').strip()
                    
                    # Сопоставляем с известными полями
                    for keyword, field_path in field_mapping.items():
                        if keyword in section_name:
                            current_field = keyword
                            found_field = True
                            break
                
                # Обработка многострочных значений
                if not found_field and current_field and current_field in field_mapping and line.strip():
                    field_path = field_mapping[current_field]
                    if isinstance(field_path, list):
                        field_path = field_path[0]
                    
                    # Проверяем, не является ли строка началом нового блока
                    is_new_block = any(line_lower.startswith(keyword) for keyword in field_mapping.keys())
                    
                    if not is_new_block and not is_list_item and not in_list:
                        self._add_to_result(result, field_path, line.strip())
                
                # Если это не структурированный текст и не нашли поле, пробуем угадать по контексту
                if not is_structured and not found_field and not current_field:
                    for keyword, field_path in field_mapping.items():
                        if keyword in line_lower:
                            if isinstance(field_path, list):
                                field_path = field_path[0]
                            self._add_to_result(result, field_path, line)
                            current_field = keyword
                            break
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении структурированной информации: {e}")
            logger.debug(f"Текст, вызвавший ошибку: {text}")
            return result


def parse_args():
    """Парсинг аргументов командной строки.
    
    Returns:
        Namespace: Объект с разобранными аргументами командной строки.
    """
    # Сначала загружаем переменные окружения, чтобы использовать их как значения по умолчанию
    load_dotenv()
    default_export_path = os.getenv('CHAT_EXPORT_PATH') or settings.chat_export_path
    
    parser = argparse.ArgumentParser(description='Анализ чата с помощью LLM')
    parser.add_argument('--input', '-i', type=str, default=default_export_path,
                        help=f'Путь к файлу с экспортом чата (JSON). По умолчанию: {default_export_path}')
    parser.add_argument('--output', '-o', type=str, default='chat_analysis_report.txt',
                        help='Имя файла для сохранения отчета (по умолчанию: chat_analysis_report.txt)')
    
    return parser.parse_args()


async def main():
    """Основная функция для запуска анализа чата."""
    logger.info("=== Начало работы скрипта анализа чата ===")
    
    try:
        # Парсим аргументы командной строки (включая загрузку переменных окружения)
        logger.info("Обработка аргументов командной строки...")
        args = parse_args()
        chat_export_path = args.input
        output_file = args.output
        
        logger.info(f"Используемый путь к файлу: {chat_export_path}")
        logger.info(f"Файл для сохранения отчета: {output_file}")
        
        # Проверяем существование файла
        if not os.path.exists(chat_export_path):
            error_msg = f"Файл с экспортом чата не найден: {chat_export_path}"
            logger.error(error_msg)
            print(f"Ошибка: {error_msg}")
            return 1
        
        # Загружаем данные из файла
        logger.info("Загрузка данных из файла...")
        try:
            with open(chat_export_path, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            
            # Проверяем структуру загруженных данных
            if not isinstance(chat_data, dict):
                raise ValueError("Некорректный формат данных: ожидался словарь")
                
            if 'messages' not in chat_data:
                logger.warning("В данных не найден ключ 'messages'. Пытаемся продолжить...")
                
            logger.info(f"Загружено сообщений: {len(chat_data.get('messages', []))}")
            
        except json.JSONDecodeError as e:
            error_msg = f"Ошибка при разборе JSON: {str(e)}"
            logger.error(error_msg)
            print(f"Ошибка: {error_msg}")
            return 1
        except Exception as e:
            error_msg = f"Ошибка при загрузке файла: {str(e)}"
            logger.error(error_msg)
            print(f"Ошибка: {error_msg}")
            return 1
        
        # Инициализируем анализатор
        logger.info("Инициализация анализатора чата...")
        analyzer = ChatAnalyzerLLM()
        
        # Запускаем анализ
        logger.info(f"Запуск анализа чата из файла: {chat_export_path}")
        try:
            logger.info("=== Начало анализа чата ===")
            result = await analyzer.analyze_chat(chat_data)
            logger.info(f"Результат анализа: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            # Проверяем результат анализа
            if not result:
                logger.error("Анализ завершился с пустым результатом")
                print("Ошибка: Анализ завершился с пустым результатом")
                return 1
                
            if 'error' in result:
                logger.error(f"Ошибка при анализе: {result['error']}")
                print(f"Ошибка: {result['error']}")
                return 1
                
            # Выводим основную информацию о результате
            logger.info("\n=== Результат анализа ===")
            logger.info(f"Статус: {result.get('status', 'не указан')}")
            logger.info(f"Найдено участников: {len(result.get('results', {}))}")
            
            # Проверяем наличие отчета в результате
            logger.info("Проверка результата анализа...")
            if not result:
                logger.error("Результат анализа пуст")
                print("Ошибка: Не удалось получить результат анализа")
                return 1
                
            if 'error' in result:
                logger.error(f"Ошибка в результате анализа: {result['error']}")
                print(f"Ошибка: {result['error']}")
                return 1
                
            # Сохранение отчета в файл с правильной кодировкой
            try:
                # Создаем папку для отчетов, если её нет
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8-sig') as f:
                    if 'report' in result and result['report']:
                        f.write(result['report'])
                        logger.info(f"Отчет успешно сохранен в файл: {output_file}")
                        print(f"Отчет успешно сохранен в файл: {output_file}")
                        return 0
                    else:
                        error_msg = "Не удалось сгенерировать отчет: отсутствуют данные отчета"
                        logger.error(error_msg)
                        print(f"Ошибка: {error_msg}")
                        return 1
                        
            except Exception as e:
                error_msg = f"Ошибка при сохранении отчета: {str(e)}"
                logger.error(error_msg)
                if 'report' in result:
                    logger.error(f"Тип данных отчета: {type(result['report'])}")
                    if result['report']:
                        logger.error(f"Длина отчета: {len(result['report'])} символов")
                        logger.error(f"Первые 500 символов: {result['report'][:500]}")
                print(f"Ошибка: {error_msg}")
                return 1
            
        except Exception as e:
            error_msg = f"Ошибка при анализе чата: {str(e)}"
            logger.error(error_msg, exc_info=True)
            print(f"Ошибка: {error_msg}")
            return 1
        
    except Exception as e:
        error_msg = f"Критическая ошибка: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"Ошибка: {error_msg}")
        return 1
    
    return 0


if __name__ == "__main__":
    # Запускаем асинхронную функцию
    sys.exit(asyncio.run(main()))
