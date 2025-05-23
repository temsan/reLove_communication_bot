"""
Модуль для анализа чата с помощью LLM.
Анализирует сообщения из чата reLove, выделяя ключевые темы, эмоции и инсайты.
"""
import asyncio
import json
import logging
import os
import re
import sys
import traceback
import warnings
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from tqdm import tqdm
from tqdm import trange
import time
import httpx
from dotenv import load_dotenv
import argparse

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chat_analysis.log', encoding='utf-8'),
        # logging.StreamHandler()  # УБРАНО: не выводим логи в консоль
    ]
)

# Отключаем вывод сообщений в лог
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Отключаем предупреждения transformers
warnings.filterwarnings("ignore", category=FutureWarning)

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from relove_bot.services.llm_service import LLMService
from relove_bot.services.prompts import PSYCHOLOGICAL_ANALYSIS_PROMPT, get_analysis_prompt
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
        self.llm_service = LLMService()
        self.token_monitor = TokenLimitMonitor()
        self.current_model_index = 0
        
        # Настройки API
        self.api_base = "https://openrouter.ai/api/v1"
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        self.model = self.FREE_MODELS[0]
        self.max_tokens = 1000
        self.temperature = 0.7
        self.max_retries = 1
        self.retry_delay = 0
        
        # Настройки запросов
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://relove.com",
            "X-Title": "reLove Bot"
        }
        
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
        
    async def _make_llm_request(self, prompt: str, model: str = None) -> Optional[str]:
        """Делает запрос к LLM с обработкой ошибок"""
        try:
            logger.info("=== Детали запроса к LLM ===")
            logger.info(f"URL: {self.api_base}/chat/completions")
            logger.info(f"Модель: {model or self.model}")
            logger.info(f"Размер промпта: {len(prompt)} символов")
            logger.info("==========================")
            for attempt in range(self.max_retries):
                try:
                    payload = {
                        "model": model or self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens
                    }
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{self.api_base}/chat/completions",
                            headers=self.headers,
                            json=payload,
                            timeout=30
                        )
                        if response.status_code != 200:
                            error_msg = response.json().get('error', {}).get('message', 'Unknown error')
                            if 'Rate limit' in error_msg or "free-models-per" in error_msg:
                                logger.warning(f"Превышение лимита API, попытка {attempt + 1}/{self.max_retries}")
                                next_model = self._get_next_model()
                                if next_model:
                                    logger.info(f"Переключаемся на модель: {next_model}")
                                    return await self._make_llm_request(prompt, next_model)
                                continue
                            raise ValueError(f"Ошибка API: {error_msg}")
                        result = response.json()
                        if not result or not result.get('choices'):
                            raise ValueError("Пустой ответ от API")
                        content = result['choices'][0]['message'].get('content')
                        if not content:
                            raise ValueError("Пустой контент в ответе")
                        return content
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        logger.error(f"Ошибка при генерации текста после {self.max_retries} попыток: {str(e)}")
                        raise
                    logger.warning(f"Ошибка при попытке {attempt + 1}/{self.max_retries}: {str(e)}")
                    continue
        except Exception as e:
            logger.error(f"Ошибка при генерации текста: {str(e)}")
            raise
        
    async def _analyze_user_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Анализирует сообщения одного пользователя.
        
        Args:
            messages: Список сообщений
            
        Returns:
            Dict[str, Any]: Результаты анализа или словарь с ошибкой
        """
        try:
            # Формируем текст сообщений с временными метками
            messages_text = "\n".join([
                f"{msg.get('date', '')}: {self._extract_text(msg)}"
                for msg in messages
                if self._extract_text(msg).strip()
            ])

            # Создаем четкий промпт для LLM
            prompt = f"""Анализ сообщений пользователя из чата.

Сообщения:
{messages_text}

Создай структурированный анализ в формате JSON строго по следующей схеме:
{{
    "name": "Имя пользователя из сообщений, если не найдено - 'Неизвестный участник'",
    "темы": ["список основных тем, которые обсуждает пользователь"],
    "эмоции": ["список эмоций, которые проявляются в сообщениях"],
    "инсайты": ["список осознаний или открытий пользователя"],
    "вопросы": ["список вопросов, которые задает пользователь"],
    "трудности": ["список проблем или сложностей, о которых говорит пользователь"],
    "рекомендации": ["список рекомендаций для дальнейшей работы с пользователем"]
}}

Важно: 
1. Все поля, кроме name, должны быть непустыми списками
2. Если для какого-то поля нет данных, используй пустой список []
3. Ответ должен быть только в формате JSON
4. Все значения должны быть на русском языке"""

            # Отправляем запрос к LLM с обработкой ошибок
            response = await self._make_llm_request(prompt)
            if not response:
                logger.error("Пустой ответ от LLM")
                return {"error": "Не удалось получить ответ от LLM"}

            # Очищаем ответ от маркеров кода
            response = response.strip()
            for marker in ["```json", "```"]:
                if response.startswith(marker):
                    response = response[len(marker):]
                if response.endswith(marker):
                    response = response[:-len(marker)]
            response = response.strip()

            try:
                # Парсим JSON с проверкой структуры
                result = json.loads(response)
                
                # Проверяем все ли поля на месте и правильного типа
                required_fields = ["name", "темы", "эмоции", "инсайты", "вопросы", "трудности", "рекомендации"]
                for field in required_fields:
                    if field not in result:
                        result[field] = [] if field != "name" else "Неизвестный участник"
                    elif field != "name" and not isinstance(result[field], list):
                        result[field] = [str(result[field])] if result[field] else []

                # Проверяем и нормализуем поле name
                if not isinstance(result["name"], str) or not result["name"].strip():
                    result["name"] = "Неизвестный участник"
                
                return result

            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON: {e}")
                logger.debug(f"Проблемный ответ LLM: {response}")
                # Попробуем создать валидную структуру из текста
                return self._extract_structured_info_from_text(response)

        except Exception as e:
            logger.error(f"Ошибка при анализе сообщений пользователя: {e}")
            return {"error": str(e)}

    def _extract_structured_info_from_text(self, text: str) -> Dict[str, Any]:
        """
        Пытается извлечь структурированную информацию из текстового ответа,
        когда не удалось распарсить JSON.
        """
        result = {
            "name": "Неизвестный участник",
            "темы": [],
            "эмоции": [],
            "инсайты": [],
            "вопросы": [],
            "трудности": [],
            "рекомендации": []
        }

        try:
            # Ищем секции в тексте
            sections = {
                "темы": ["темы:", "темы -", "основные темы:"],
                "эмоции": ["эмоции:", "эмоции -", "эмоциональный фон:"],
                "инсайты": ["инсайты:", "инсайты -", "осознания:"],
                "вопросы": ["вопросы:", "вопросы -"],
                "трудности": ["трудности:", "трудности -", "сложности:", "проблемы:"],
                "рекомендации": ["рекомендации:", "рекомендации -", "советы:"]
            }

            lines = text.split('\n')
            current_section = None

            for line in lines:
                line = line.strip().lower()
                if not line:
                    continue

                # Определяем секцию
                for section, markers in sections.items():
                    if any(line.startswith(marker) for marker in markers):
                        current_section = section
                        continue

                # Добавляем контент в текущую секцию
                if current_section and line and not any(line.startswith(m) for m in sum(sections.values(), [])):
                    # Убираем маркеры списка и очищаем строку
                    content = line.lstrip('•-*').strip()
                    if content:
                        result[current_section].append(content)

            # Удаляем дубликаты и пустые значения
            for key in result:
                if isinstance(result[key], list):
                    result[key] = list(dict.fromkeys(filter(None, result[key])))

            return result

        except Exception as e:
            logger.error(f"Ошибка при извлечении структуры из текста: {e}")
            return result
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """Возвращает структуру анализа по умолчанию."""
        return {
            "имя": "Неизвестный участник",
            "темы": [],
            "эмоции": [],
            "инсайты": [],
            "вопросы": [],
            "трудности": [],
            "рекомендации": []
        }

    def _group_by_user(self, messages: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Группирует сообщения по пользователям."""
        user_messages = defaultdict(list)
        
        for msg in messages:
            # Извлекаем ID пользователя
            user_id = msg.get('from_id', None)
            
            # Если нет from_id, пытаемся использовать поле from
            if not user_id and 'from' in msg:
                from_field = msg['from']
                if isinstance(from_field, str) and from_field.startswith('user'):
                    user_id = from_field
                elif isinstance(from_field, dict):
                    user_id = str(from_field.get('id', None))
            
            if user_id:
                user_messages[user_id].append(msg)
        
        return dict(user_messages)

    def _extract_text(self, msg: Dict[str, Any]) -> str:
        """Извлекает текст из сообщения."""
        # Проверяем варианты полей с текстом
        text = msg.get('text', msg.get('message', ''))
        
        # Если это словарь или список, пытаемся преобразовать в строку
        if isinstance(text, (dict, list)):
            try:
                text = json.dumps(text, ensure_ascii=False)
            except:
                text = str(text)
        
        # Убираем избыточные пробелы и переносы строк
        text = ' '.join(str(text).split())
        return text

    def _get_user_info(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Извлекает информацию о пользователе из сообщения."""
        try:
            # Пытаемся получить информацию из поля from
            if 'from' in message:
                from_field = message['from']
                if isinstance(from_field, dict):
                    return {
                        'id': str(from_field.get('id')),
                        'name': from_field.get('first_name', '') + ' ' + from_field.get('last_name', ''),
                        'username': from_field.get('username', '')
                    }
                elif isinstance(from_field, str):
                    return {
                        'id': from_field,
                        'name': 'Неизвестный участник',
                        'username': ''
                    }
            
            # Пытаемся получить информацию из других полей
            user_id = message.get('from_id', message.get('user_id', ''))
            name = message.get('name', message.get('full_name', 'Неизвестный участник'))
            username = message.get('username', '')
            
            return {
                'id': str(user_id) if user_id else '',
                'name': name.strip() if name else 'Неизвестный участник',
                'username': username if username else ''
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе: {e}")
            return {
                'id': '',
                'name': 'Неизвестный участник',
                'username': ''
            }

    async def analyze_chat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Анализирует чат с использованием LLM для определения психологических профилей участников."""
        if not data or 'messages' not in data:
            logger.error("Нет данных для анализа: data пуст или отсутствует ключ 'messages'")
            return {"error": "Нет сообщений для анализа"}
            
        try:
            messages = data['messages']
            if not messages:
                logger.error("Список сообщений пуст")
                return {"error": "Нет сообщений для анализа"}
            
            # Группируем сообщения по пользователям
            user_messages = self._group_by_user(messages)
            logger.info(f"Найдено уникальных пользователей: {len(user_messages)}")
            
            if not user_messages:
                logger.error("Не удалось сгруппировать сообщения по пользователям")
                return {"error": "Не удалось определить пользователей"}
            
            # Анализируем каждого пользователя
            results = {}
            for user_id, msgs in user_messages.items():
                try:
                    user_info = self._get_user_info(msgs[0])
                    # Анализируем сообщения пользователя
                    analysis = await self._analyze_with_prompt(msgs, user_info, "event")
                    if isinstance(analysis, dict) and not analysis.get('error'):
                        results[user_id] = analysis
                except Exception as e:
                    logger.error(f"Ошибка при анализе пользователя {user_id}: {str(e)}")
                    continue
            
            if not results:
                return {"error": "Не удалось проанализировать ни одного пользователя"}
            
            # Генерируем текст отчета
            report_text = self._generate_text_report(results)
            
            # Собираем статистику
            stats = {
                "total_messages": len(messages),
                "total_users": len(user_messages),
                "analyzed_users": len(results),
            }
            
            return {
                "status": "success",
                "results": results,
                "report": report_text,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Ошибка при анализе чата: {str(e)}")
            return {"error": f"Ошибка при анализе чата: {str(e)}"}

    def _generate_text_report(self, results: Dict[str, Any]) -> str:
        """Генерирует текстовый отчет."""
        try:
            report_lines = ["=== АНАЛИЗ ЧАТА ===\n"]
            
            # Добавляем статистику
            report_lines.extend([
                "ОБЩАЯ СТАТИСТИКА:",
                f"Всего участников: {len(results)}",
                ""
            ])
            
            # Анализ по участникам
            report_lines.append("АНАЛИЗ ПО УЧАСТНИКАМ:")
            for user_id, profile in results.items():
                report_lines.extend([
                    "",
                    f"--- {profile['имя']} ---",
                    f"Темы: {', '.join(profile['темы']) if profile['темы'] else 'не выявлены'}",
                    f"Эмоции: {', '.join(profile['эмоции']) if profile['эмоции'] else 'не выявлены'}",
                    "Инсайты:"
                ])
                for insight in profile['инсайты']:
                    report_lines.append(f"- {insight}")
                
                if profile['вопросы']:
                    report_lines.append("Вопросы:")
                    for q in profile['вопросы']:
                        report_lines.append(f"- {q}")
                
                if profile['трудности']:
                    report_lines.append("Трудности:")
                    for d in profile['трудности']:
                        report_lines.append(f"- {d}")
                        
                if profile['рекомендации']:
                    report_lines.append("Рекомендации:")
                    for r in profile['рекомендации']:
                        report_lines.append(f"- {r}")
            
            return "\n".join(report_lines)
            
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            return "Ошибка при генерации отчета"

    async def _analyze_with_prompt(self, messages: List[Dict[str, Any]], user_info: Dict[str, Any], prompt_type: str) -> Dict[str, Any]:
        """Анализирует сообщения с определенным типом промпта."""
        try:
            # Формируем текст сообщений
            messages_text = "\n".join([
                f"{msg.get('date', '')}: {self._extract_text(msg)}"
                for msg in messages
                if self._extract_text(msg).strip()
            ])

            # Выбираем тип промпта и создаем базу для анализа
            base_prompt = f"Проанализируй сообщения пользователя {user_info.get('name', 'Неизвестный участник')}.\n\n"
            base_prompt += f"Сообщения:\n{messages_text}\n\n"

            if prompt_type == "event":
                base_prompt += """Создай анализ в формате JSON:
{
    "имя": "Имя пользователя",
    "темы": ["список тем"],
    "эмоции": ["список эмоций"],
    "инсайты": ["список инсайтов"],
    "вопросы": ["список вопросов"],
    "трудности": ["список трудностей"],
    "рекомендации": ["список рекомендаций"]
}"""
            elif prompt_type == "mirror":
                base_prompt += """Создай глубокий психологический анализ в формате JSON:
{
    "имя": "Имя пользователя",
    "темы": ["психологические темы"],
    "эмоции": ["глубинные эмоции"],
    "инсайты": ["психологические инсайты"],
    "вопросы": ["важные вопросы"],
    "трудности": ["психологические трудности"],
    "рекомендации": ["терапевтические рекомендации"]
}"""
            else:  # relove
                base_prompt += """Создай поддерживающий анализ в формате JSON:
{
    "имя": "Имя пользователя",
    "темы": ["позитивные темы"],
    "эмоции": ["ресурсные эмоции"],
    "инсайты": ["вдохновляющие инсайты"],
    "вопросы": ["развивающие вопросы"],
    "трудности": ["зоны роста"],
    "рекомендации": ["поддерживающие рекомендации"]
}"""

            # Отправляем запрос к LLM
            response = await self._make_llm_request(base_prompt)

            # Парсим и валидируем ответ
            try:
                response = response.strip().strip('```json').strip('```').strip()
                result = json.loads(response)

                # Нормализуем поля
                return {
                    "имя": result.get("имя", user_info.get("name", "Неизвестный участник")),
                    "темы": result.get("темы", []),
                    "эмоции": result.get("эмоции", []),
                    "инсайты": result.get("инсайты", []),
                    "вопросы": result.get("вопросы", []),
                    "трудности": result.get("трудности", []),
                    "рекомендации": result.get("рекомендации", [])
                }

            except json.JSONDecodeError:
                return self._extract_structured_info_from_text(response)

        except Exception as e:
            logger.error(f"Ошибка в _analyze_with_prompt: {e}")
            return self._get_default_analysis()
