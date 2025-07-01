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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from tqdm import tqdm
from dotenv import load_dotenv
import glob
from pathlib import Path

# === ДОБАВЛЕНО: импорт для LLM ===
from relove_bot.services.llm_service import llm_service

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path('temp/chat_analysis.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)
logger.info("Инициализация скрипта анализа чата")

class AnalysisCache:
    """Класс для кеширования результатов анализа чата.
    
    Структура кеша:
    .analysis_cache/
    ├── files/                  # Хеши файлов
    │   └── {file_hash}.json    # Метаданные файла
    └── users/                  # Данные пользователей
        └── {user_id}/          # ID пользователя
            ├── {hash1}.json    # Результаты анализа
            └── {hash2}.json
    """
    
    def __init__(self, cache_dir: str = '.analysis_cache'):
        """Инициализирует кеш анализа.
        
        Args:
            cache_dir: Базовая директория для хранения кеша
        """
        self.cache_dir = Path(cache_dir)
        self.files_dir = self.cache_dir / 'files'
        self.users_dir = self.cache_dir / 'users'
        
        # Создаем необходимые директории
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.users_dir.mkdir(exist_ok=True)
        
        logger.info(f"Инициализирован кеш в директории: {self.cache_dir.absolute()}")
        logger.info(f"Файлы: {self.files_dir}")
        logger.info(f"Пользователи: {self.users_dir}")  # Загружаем существующий индекс
    
    def _get_file_hash(self, file_path: Union[str, Path]) -> str:
        """Вычисляет MD5 хеш содержимого файла."""
        file_path = Path(file_path)
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def get_file_hash(self, file_path: Union[str, Path]) -> str:
        """Вычисляет хеш файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Строковый хеш файла
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
            
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
        
    def get_messages_hash(self, messages: List[Dict[str, Any]]) -> str:
        """Генерирует хеш на основе сообщений пользователя.
        
        Args:
            messages: Список сообщений пользователя
            
        Returns:
            Строковый хеш для идентификации набора сообщений
        """
        if not messages:
            return "empty"
            
        # Сортируем сообщения по дате для консистентности
        sorted_messages = sorted(
            (msg for msg in messages if isinstance(msg, dict)),
            key=lambda x: (x.get('date', ''), str(x.get('message_id', '')))
        )
        
        # Создаем строку для хеширования
        hash_components = [f"total={len(sorted_messages)}"]
        
        # Добавляем хешированные части сообщений
        for msg in sorted_messages:
            msg_text = str(msg.get('text', ''))
            msg_date = str(msg.get('date', ''))
            msg_id = str(msg.get('message_id', ''))
            
            # Хешируем длинные тексты для экономии места
            if len(msg_text) > 100:
                msg_text = hashlib.md5(msg_text.encode()).hexdigest()
                
            hash_components.append(f"{msg_date}:{msg_id}:{msg_text[:100]}")
        
        # Хешируем финальную строку
        hash_input = "|".join(hash_components).encode()
        return hashlib.md5(hash_input).hexdigest()
    
    def load_result(self, file_hash: str, user_id: str, messages_hash: str) -> Optional[Dict]:
        """Загружает результат анализа из кеша.
        
        Args:
            file_hash: Хеш исходного файла
            user_id: ID пользователя
            messages_hash: Хеш сообщений пользователя
            
        Returns:
            Словарь с результатом анализа или None, если не найден
        """
        try:
            # Проверяем, есть ли такой файл в кеше
            file_meta_path = self.files_dir / f"{file_hash}.json"
            if not file_meta_path.exists():
                return None
                
            # Проверяем, есть ли у пользователя такой хеш сообщений
            user_dir = self.users_dir / str(user_id)
            if not user_dir.exists():
                return None
                
            cache_file = user_dir / f"{messages_hash}.json"
            if not cache_file.exists():
                return None
                
            # Загружаем кешированный результат
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Проверяем актуальность кеша
            with open(file_meta_path, 'r', encoding='utf-8') as f:
                file_meta = json.load(f)
                
            if data.get('file_version') != file_meta.get('version'):
                logger.debug(f"Версия файла изменилась, кеш устарел: {file_hash}")
                return None
                
            logger.debug(f"Загружен кеш для пользователя {user_id}, хеш: {messages_hash}")
            return data.get('result')
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке из кеша: {e}", exc_info=True)
            return None
    
    def save_result(self, file_path: Union[str, Path], user_id: str, 
                    messages: List[Dict[str, Any]], result: Dict) -> bool:
        """Сохраняет результат анализа в кеш.
        
        Args:
            file_path: Путь к исходному файлу
            user_id: ID пользователя
            messages: Список сообщений пользователя
            result: Результат анализа
            
        Returns:
            bool: True если сохранение прошло успешно
        """
        try:
            file_path = Path(file_path)
            file_hash = self.get_file_hash(file_path)
            messages_hash = self.get_messages_hash(messages)
            
            # Создаем директорию пользователя, если её нет
            user_dir = self.users_dir / str(user_id)
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # Путь к файлу с результатом
            cache_file = user_dir / f"{messages_hash}.json"
            
            # Путь к метаданным файла
            file_meta_path = self.files_dir / f"{file_hash}.json"
            
            # Создаем/обновляем метаданные файла
            file_meta = {
                'file_path': str(file_path.absolute()),
                'file_size': file_path.stat().st_size,
                'last_modified': file_path.stat().st_mtime,
                'version': 1,  # Можно увеличивать при изменении формата
                'cached_at': datetime.now().isoformat()
            }
            
            # Сохраняем метаданные файла
            with open(file_meta_path, 'w', encoding='utf-8') as f:
                json.dump(file_meta, f, ensure_ascii=False, indent=2)
            
            # Сохраняем результат анализа
            cache_data = {
                'user_id': user_id,
                'file_hash': file_hash,
                'messages_hash': messages_hash,
                'messages_count': len(messages),
                'first_message_date': messages[0].get('date') if messages else None,
                'last_message_date': messages[-1].get('date') if messages else None,
                'file_version': file_meta['version'],
                'cached_at': datetime.now().isoformat(),
                'result': result
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Сохранен кеш для пользователя {user_id}, хеш: {messages_hash}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении в кеш: {e}", exc_info=True)
            return False
    
    def clear_old_cache(self, max_age_days: int = 30) -> int:
        """Очищает устаревшие записи кеша.
        
        Args:
            max_age_days: Максимальный возраст записи в днях
            
        Returns:
            int: Количество удаленных записей
        """
        deleted = 0
        now = datetime.now()
        max_age = timedelta(days=max_age_days)
        
        # Очищаем устаревшие файлы пользователей
        for user_dir in self.users_dir.glob('*'):
            if user_dir.is_dir():
                for cache_file in user_dir.glob('*.json'):
                    try:
                        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                        if now - mtime > max_age:
                            cache_file.unlink()
                            deleted += 1
                    except Exception as e:
                        logger.error(f"Ошибка при удалении {cache_file}: {e}")
        
        # Очищаем устаревшие метаданные файлов
        for meta_file in self.files_dir.glob('*.json'):
            try:
                mtime = datetime.fromtimestamp(meta_file.stat().st_mtime)
                if now - mtime > max_age:
                    meta_file.unlink()
                    deleted += 1
            except Exception as e:
                logger.error(f"Ошибка при удалении {meta_file}: {e}")
        
        return deleted

    def _process_llm_response(self, response_text: str, username: str):
        """Обрабатывает ответ от LLM и возвращает структурированные данные.
        
        Args:
            response_text: Текст ответа от LLM
            username: Имя пользователя для логирования
            
        Returns:
            Словарь с результатами анализа
        """
        try:
            # Логируем сырой ответ для отладки
            logger.debug(f"Сырой ответ от LLM: {response_text[:500]}..." if len(response_text) > 500 
                        else f"Сырой ответ от LLM: {response_text}")
            
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
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе: {e}")
            return {
                'id': '',
                'name': 'Участник',
                'username': ''
            }

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
        
        Возвращает:
            dict: Словарь с ключами:
                - id: ID пользователя (из from_id или user_id)
                - name: Полное имя пользователя
                - username: Имя пользователя (если есть)
        """
        try:
            # Инициализируем переменные
            user_id = ''
            name = ''
            username = ''
            
            # Получаем ID пользователя из разных возможных полей
            if 'from_id' in message:
                user_id = str(message['from_id'])
            elif 'user_id' in message:
                user_id = str(message['user_id'])
            
            # Получаем имя пользователя
            if 'from' in message and isinstance(message['from'], str):
                name = message['from']
            elif 'name' in message:
                name = str(message['name'])
            
            # Получаем username, если есть
            if 'username' in message:
                username = str(message['username'])
            
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

    def _handle_analysis_error(self, error_msg: str, report_path: str = None) -> Dict[str, Any]:
        """Обрабатывает ошибку при анализе и возвращает словарь с информацией об ошибке.
        
        Args:
            error_msg: Сообщение об ошибке
            report_path: Путь к файлу отчета (опционально)
            
        Returns:
            Словарь с информацией об ошибке
        """
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        result = {"error": error_msg}
        if report_path:
            result["report_path"] = str(report_path)
            
        return result

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
                # Получаем имя из actor или из первого сообщения
                actor_name = None
                for msg in profile.get('messages', []):
                    if 'actor' in msg and msg['actor']:
                        actor_name = msg['actor']
                        break
                    if 'from' in msg and isinstance(msg['from'], str) and msg['from']:
                        actor_name = msg['from']
                        break
                if actor_name:
                    username = actor_name.strip()
                else:
                    # Используем имя из профиля, если оно есть
                    username = profile.get('name', '').strip()
                    # Если имя пустое или неизвестное, используем ID
                    if not username or username.lower() in ['неизвестный', 'unknown']:
                        username = f'Участник {user_id}'
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
    default_export_path = os.getenv('CHAT_EXPORT_PATH')
    
    # Текущая дата по умолчанию
    current_date = datetime.now()
    
    # Создаем парсер аргументов
    parser = argparse.ArgumentParser(description='Анализ чата с помощью LLM')
    
    # Основные аргументы
    default_input = os.getenv('CHAT_EXPORT_PATH')
    parser.add_argument(
        '--input',
        type=str,
        required=not bool(default_input),
        default=default_input,
        help='Путь к входному JSON-файлу с сообщениями чата или директории с файлами. '
             'Если не указан, берется из переменной окружения CHAT_EXPORT_PATH.'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Путь для сохранения отчета (по умолчанию: reports/analysis_<timestamp>.<json|txt>)'
    )
    
    # Параметры для формирования имени отчета
    parser.add_argument('--output-dir', type=str, default='reports',
                      help='Директория для сохранения отчетов (по умолчанию: reports)')
    
    # Опции кеширования
    cache_group = parser.add_argument_group('Настройки кеширования')
    cache_group.add_argument('--no-cache', action='store_true',
                           help='Отключить кеширование результатов анализа')
    cache_group.add_argument('--clean-cache', action='store_true',
                           help='Очистить устаревшие кеш-файлы (старше 30 дней)')
    cache_group.add_argument('--cache-dir', type=str, default='.analysis_cache',
                           help='Директория для хранения кеша (по умолчанию: .analysis_cache)')
    
    # Формат вывода
    output_group = parser.add_argument_group('Настройки вывода')
    output_group.add_argument('--format', type=str, choices=['json', 'text'], default='text',
                            help='Формат вывода отчета (json или text)')
    output_group.add_argument('--output-extension', type=str, default=None,
                            help='Расширение выходного файла (по умолчанию: .md для text, .json для json)')
    
    # Парсим аргументы
    args = parser.parse_args()
    
    # Функция для извлечения информации о чате из JSON
    def extract_chat_info(input_path):
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Извлекаем название чата и удаляем префикс 'reLove ЧАТ '
            chat_name = data.get('name', '')
            event_name = re.sub(r'^reLove\s*ЧАТ\s*', '', chat_name).strip()
            
            # Ищем дату в сообщениях
            chat_date = current_date
            for msg in data.get('messages', [])[:100]:  # Проверяем первые 100 сообщений
                if 'date' in msg:
                    try:
                        chat_date = datetime.strptime(msg['date'].split('T')[0], '%Y-%m-%d')
                        break
                    except (ValueError, IndexError):
                        continue
                        
            return event_name, chat_date
        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            logger.warning(f'Не удалось извлечь информацию из JSON: {e}')
            return 'Неизвестное событие', current_date
    
    # Извлекаем информацию о чате
    event_name, chat_date = extract_chat_info(args.input)
    
    # Словарь с русскими названиями месяцев
    month_ru = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    
    # Функция для очистки имени файла от запрещённых символов
    def sanitize_filename(filename):
        return re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Формируем имя файла: "Название_чата Месяц ГГГГ"
    filename = sanitize_filename(f"{event_name} {month_ru[chat_date.month]} {chat_date.year}.md")
    
    # Создаем директорию для отчетов, если её нет
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Определяем расширение файла на основе формата
    if args.output_extension:
        file_extension = args.output_extension
    else:
        file_extension = '.json' if args.format == 'json' else '.md'
    
    # Убираем существующее расширение, если оно есть
    base_filename = os.path.splitext(filename)[0]
    
    # Добавляем полный путь к файлу отчета в аргументы
    args.report_path = output_dir / f"{base_filename}{file_extension}"
    
    return args


async def main():
    """Основная функция для запуска анализа чата."""
    logger.info("=== Начало работы скрипта анализа чата ===")
    try:
        # Парсим аргументы командной строки
        logger.info("Обработка аргументов командной строки...")
        args = parse_args()
        chat_export_path = Path(args.input)
        output_file = Path(args.report_path)

        logger.info(f"Используемый путь к файлу/папке: {chat_export_path.absolute()}")
        logger.info(f"Файл для сохранения отчета: {output_file.absolute()}")

        if not chat_export_path.exists():
            error_msg = f"Путь не найден: {chat_export_path.absolute()}"
            logger.error(error_msg)
            print(f"Ошибка: {error_msg}")
            return 1

        if chat_export_path.is_dir():
            # Корректно получаем все .json-файлы в папке, избегая ошибок прав
            all_messages = []
            json_files = []
            for fname in os.listdir(chat_export_path):
                fpath = chat_export_path / fname
                if fpath.is_file() and fpath.suffix == '.json':
                    json_files.append(fpath)
            if not json_files:
                print(f"В директории {chat_export_path} не найдено .json файлов!")
                return 1
            print(f"Найдено файлов для анализа: {len(json_files)}")
            for file_path in json_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    msgs = data.get('messages', [])
                    all_messages.extend(msgs)
                except Exception as e:
                    print(f"Ошибка при чтении файла {file_path}: {e}")
            if not all_messages:
                print("Нет сообщений для анализа!")
                return 1
            analyzer = ChatAnalyzerLLM()
            results = await analyzer.analyze_chat({'messages': all_messages})
            report = results['report']
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8-sig') as f:
                f.write(report)
            print(f"Общий отчёт сохранён: {output_file}")
            if not output_file.exists() or output_file.stat().st_size == 0:
                print(f"ВНИМАНИЕ: Файл отчёта не создан или пустой: {output_file}")
            else:
                print("Анализ завершён! Отчёт успешно сформирован.")
            return 0
        elif chat_export_path.is_file():
            # Путь — это файл, анализируем только его
            try:
                with open(chat_export_path, 'r', encoding='utf-8') as f:
                    chat_data = json.load(f)
                if not isinstance(chat_data, dict):
                    raise ValueError("Некорректный формат данных: ожидался словарь")
                if 'messages' not in chat_data:
                    logger.warning("В данных не найден ключ 'messages'. Пытаемся продолжить...")
                logger.info(f"Загружено сообщений: {len(chat_data.get('messages', []))}")
            except Exception as e:
                error_msg = f"Ошибка при загрузке файла: {str(e)}"
                logger.error(error_msg)
                print(f"Ошибка: {error_msg}")
                return 1
            analyzer = ChatAnalyzerLLM()
            results = await analyzer.analyze_chat(chat_data)
            report = results['report']
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8-sig') as f:
                f.write(report)
            print(f"Отчёт сохранён: {output_file}")
            if not output_file.exists() or output_file.stat().st_size == 0:
                print(f"ВНИМАНИЕ: Файл отчёта не создан или пустой: {output_file}")
            else:
                print("Анализ завершён! Отчёт успешно сформирован.")
            return 0
        else:
            error_msg = f"Путь {chat_export_path} не является ни файлом, ни папкой."
            logger.error(error_msg)
            print(f"Ошибка: {error_msg}")
            return 1
    except Exception as e:
        logger.error(f"Ошибка при выполнении анализа: {str(e)}")
        print(f"Ошибка: {e}")
        return 1


class ChatAnalyzerLLM:
    async def analyze_chat(self, chat_data, use_cache=True, output_format='md'):
        messages = chat_data.get('messages', [])
        users = {}
        for msg in messages:
            user_id = str(msg.get("from_id") or msg.get("user_id") or msg.get("from", "unknown"))
            users.setdefault(user_id, []).append(msg)
        results = {}
        def msg_text_to_str(msg):
            t = msg.get("text") or msg.get("message") or ""
            if isinstance(t, list):
                parts = []
                for x in t:
                    if isinstance(x, str):
                        parts.append(x)
                    elif isinstance(x, dict):
                        # Если есть вложенный текст
                        if 'text' in x:
                            parts.append(str(x['text']))
                return " ".join(parts)
            return str(t)
        for user_id, user_messages in users.items():
            user_text = "\n".join([msg_text_to_str(msg) for msg in user_messages if msg.get("text")])
            prompt = (
                "На основе сообщений пользователя, пожалуйста, кратко и своими словами ответь на два вопроса:\n"
                "1. Почему человек пришёл в Релав? Опиши его внутреннюю мотивацию или проблему, которая его привела.\n"
                "2. Какой результат или изменения он/она получил(а) после участия?\n"
                "Не копируй текст пользователя, а сделай выводы и обобщения.\n"
                f"\n\nСообщения пользователя:\n{user_text}"
            )
            batch_size = len(user_messages)
            while batch_size > 0:
                try:
                    analysis = await llm_service.analyze_text(prompt=prompt, system_prompt=None, max_tokens=512)
                    results[user_id] = {"analysis": analysis, "messages": user_messages}
                    break
                except Exception as e:
                    err_str = str(e)
                    if 'maximum context length' in err_str or 'context length' in err_str or 'token' in err_str:
                        # Слишком много токенов — уменьшаем батч
                        if batch_size > 10:
                            batch_size = batch_size // 2
                        else:
                            batch_size -= 1
                        if batch_size <= 0:
                            results[user_id] = {"analysis": "Ошибка: слишком много данных для анализа", "messages": user_messages}
                            break
                        # Формируем новый батч
                        batch_msgs = user_messages[:batch_size]
                        user_text = "\n".join([msg_text_to_str(msg) for msg in batch_msgs if msg.get("text")])
                        prompt = (
                            "На основе сообщений пользователя, пожалуйста, кратко и своими словами ответь на два вопроса:\n"
                            "1. Почему человек пришёл в Релав? Опиши его внутреннюю мотивацию или проблему, которая его привела.\n"
                            "2. Какой результат или изменения он/она получил(а) после участия?\n"
                            "Не копируй текст пользователя, а сделай выводы и обобщения.\n"
                            f"\n\nСообщения пользователя:\n{user_text}"
                        )
                    else:
                        results[user_id] = {"analysis": f"Ошибка: {err_str}", "messages": user_messages}
                        break
        # Собираем информацию о пользователях для отчёта
        user_info_map = {}
        for user_id, data in results.items():
            actor_name = None
            for msg in data.get('messages', []):
                if 'actor' in msg and msg['actor']:
                    actor_name = msg['actor']
                    break
                if 'from' in msg and isinstance(msg['from'], str) and msg['from']:
                    actor_name = msg['from']
                    break
            if actor_name:
                username = actor_name.strip()
            else:
                username = ''
            if not username or username.lower() in ['неизвестный', 'unknown']:
                username = f'Участник {user_id}'
            user_info_map[user_id] = username
        report = "# Общий анализ пользователей\n"
        for user_id, data in results.items():
            # Пропускаем, если нет сообщений
            if not data['messages']:
                continue
            report += f"\n## {user_info_map.get(user_id, f'Пользователь {user_id}')}\n"
            # Форматируем ответы на 2 вопроса
            answer = data['analysis']
            if isinstance(answer, str):
                report += answer.strip() + "\n"
            elif isinstance(answer, list):
                for idx, ans in enumerate(answer, 1):
                    report += f"{idx}. {ans.strip()}\n"
        return {
            'status': 'ok',
            'results': results,
            'report': report
        }


if __name__ == "__main__":
    # Запускаем асинхронную функцию
    sys.exit(asyncio.run(main()))
