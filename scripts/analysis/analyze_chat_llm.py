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
import pandas as pd
import matplotlib.pyplot as plt
import base64
import io

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
                
                # 1. ПСИХОАНАЛИТИЧЕСКИЙ АНАЛИЗ
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
                
                # 2. КОГНИТИВНЫЙ АНАЛИЗ
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
                
                # 3. ЭМОЦИОНАЛЬНЫЙ АНАЛИЗ
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
                
                # 4. ПОВЕДЕНЧЕСКИЙ АНАЛИЗ
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
                
                # 5. ИНСАЙТЫ И ВОЗМОЖНОСТИ ДЛЯ РОСТА
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
    parser.add_argument('--mode', type=str, default='short', choices=['forensic', 'short', 'both'], help='Режим анализа: short (таблица+графики, по умолчанию), forensic (структурированный), both (оба)')
    args = parser.parse_args()
    
    # Функция для извлечения информации о чате из JSON
    def extract_chat_info(input_path):
        try:
            # Если передан список файлов через запятую — берём первый
            if ',' in str(input_path):
                input_path = str(input_path).split(',')[0].strip()
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
        chat_export_path = Path(args.input) if args.input else None
        output_file = Path(args.report_path)

        # --- ДОБАВЛЕНО: поддержка списка файлов через запятую ---
        input_arg = args.input
        files = []
        if input_arg:
            if ',' in input_arg:
                files = [p.strip() for p in input_arg.split(',') if p.strip()]
            else:
                files = [input_arg.strip()]
        else:
            input_paths = os.getenv('CHAT_EXPORT_PATH')
            if input_paths:
                if ',' in input_paths:
                    files = [p.strip() for p in input_paths.split(',') if p.strip()]
                else:
                    files = [input_paths.strip()]

        if files and len(files) > 1:
            all_results = []
            all_user_rows = []
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    msgs = data.get('messages', [])
                    if not msgs:
                        print(f"Нет сообщений для анализа в файле: {file_path}")
                        continue
            analyzer = ChatAnalyzerLLM()
                    results = await analyzer.analyze_chat({'messages': msgs})
            report = results['report']
                    # Сохраняем промежуточный отчёт для каждого файла
                    file_base = os.path.splitext(os.path.basename(file_path))[0]
                    file_report_path = Path(args.output_dir) / f"report_{file_base}.md"
                    with open(file_report_path, 'w', encoding='utf-8-sig') as f:
                f.write(report)
                    # Собираем строки для общего отчёта
                    lines = report.splitlines()
                    if len(lines) > 1:
                        all_user_rows.extend([x for x in lines[1:] if x.strip()])
                except Exception as e:
                    print(f"Ошибка при анализе файла {file_path}: {e}")
            if not all_user_rows:
                print("Нет данных для объединённого анализа!")
                return 1
            # Формируем общий отчёт с агрегацией по user_id
            header = "Имя\tОтвет 1\tОтвет 2"
            user_map = {}  # user_id: {'Имя': ..., 'Ответ 1': set(), 'Ответ 2': set()}
            for row in all_user_rows:
                parts = row.split('\t')
                if len(parts) < 3:
                    continue
                name, q1, q2 = parts[0].strip(), parts[1].strip(), parts[2].strip()
                # user_id можно извлечь из имени, если имя в формате 'Участник user_id', иначе использовать имя
                user_id = name
                if name.startswith('Участник '):
                    user_id = name.split(' ', 1)[-1]
                if user_id not in user_map:
                    user_map[user_id] = {'Имя': name, 'Ответ 1': [], 'Ответ 2': []}
                if q1 and q1 not in user_map[user_id]['Ответ 1']:
                    user_map[user_id]['Ответ 1'].append(q1)
                if q2 and q2 not in user_map[user_id]['Ответ 2']:
                    user_map[user_id]['Ответ 2'].append(q2)
            # Склеиваем ответы через ;
            combined_rows = []
            for user in user_map.values():
                q1 = '; '.join(user['Ответ 1'])
                q2 = '; '.join(user['Ответ 2'])
                combined_rows.append(f"{user['Имя']}\t{q1}\t{q2}")
            combined_report = header + '\n' + '\n'.join(combined_rows)
            # --- Графики по результатам ---
            import pandas as pd
            import matplotlib.pyplot as plt
            import base64
            import io
            lines = combined_report.splitlines()
            svg_motivation = ''
            svg_result = ''
            if len(lines) > 1:
                df = pd.DataFrame([x.split('\t') for x in lines[1:] if x.strip()], columns=lines[0].split('\t'))
                # График мотиваций
                motivation_counts = df['Ответ 1'].value_counts().head(15)
                fig1, ax1 = plt.subplots(figsize=(10, 6))
                motivation_counts.plot(kind='barh', color='skyblue', ax=ax1)
                ax1.set_title('Топ-15 мотиваций прихода в reLove')
                ax1.set_xlabel('Количество')
                ax1.set_ylabel('Мотивация')
                plt.tight_layout()
                buf1 = io.BytesIO()
                plt.savefig(buf1, format='svg')
                plt.close(fig1)
                buf1.seek(0)
                svg_motivation = buf1.read().decode('utf-8')
                # График изменений
                result_counts = df['Ответ 2'].value_counts().head(15)
                fig2, ax2 = plt.subplots(figsize=(10, 6))
                result_counts.plot(kind='barh', color='lightgreen', ax=ax2)
                ax2.set_title('Топ-15 изменений после участия')
                ax2.set_xlabel('Количество')
                ax2.set_ylabel('Изменение')
                plt.tight_layout()
                buf2 = io.BytesIO()
                plt.savefig(buf2, format='svg')
                plt.close(fig2)
                buf2.seek(0)
                svg_result = buf2.read().decode('utf-8')
                # --- Markdown-таблица ---
                def tsv_to_md_table(tsv_lines):
                    rows = [line.split('\t') for line in tsv_lines if line.strip()]
                    if not rows:
                        return ''
                    header = '| ' + ' | '.join(rows[0]) + ' |'
                    sep = '| ' + ' | '.join(['---'] * len(rows[0])) + ' |'
                    body = ['| ' + ' | '.join(row) + ' |' for row in rows[1:]]
                    return '\n'.join([header, sep] + body)
                md_table = tsv_to_md_table(lines)
                # --- Итоговый md-отчёт ---
                md_report = f"""
# 📊 Аналитика reLove: мотивации и изменения

## Топ-15 мотиваций прихода
{svg_motivation}

## Топ-15 изменений после участия
{svg_result}

## Таблица ответов
{md_table}
"""
                output_file = Path(args.output_dir) / "combined_report.md"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(md_report)
                print(f'Итоговый md-отчёт сохранён: {output_file}')
            # После формирования combined_report сохраняем TSV
            tsv_path = Path(args.output_dir) / "combined_report.tsv"
            with open(tsv_path, 'w', encoding='utf-8-sig') as f:
                f.write(combined_report)
            print(f"TSV-отчёт сохранён: {tsv_path}")
            # Генерируем md-отчёт с графиками и таблицей
            md_path = Path(args.output_dir) / "combined_report.md"
            generate_md_report_with_graphs(str(tsv_path), str(md_path))
            print(f"Markdown-отчёт с графиками сохранён: {md_path}")
            return 0

        # Только если не список файлов:
        if args.input and (not files or len(files) == 1):
            chat_export_path = Path(args.input)
            logger.info(f"Используемый путь к файлу/папке: {chat_export_path.absolute()}")
            logger.info(f"Файл для сохранения отчета: {output_file.absolute()}")

        if not chat_export_path.exists():
            error_msg = f"Путь не найден: {chat_export_path.absolute()}"
            logger.error(error_msg)
            print(f"Ошибка: {error_msg}")
            return 1

        if chat_export_path.is_dir():
            # Используем glob для поиска всех .json-файлов по абсолютному пути
            import glob
            all_messages = []
            json_files = glob.glob(str(chat_export_path / '*.json'))
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
            report = await analyzer.analyze_chat(chat_data)
            # --- Формируем TSV-таблицу ---
            lines = report.strip().splitlines()
            if len(lines) > 1 and '\t' in lines[1]:
                tsv_report = report
            else:
                # Если отчёт не в TSV-формате, пропускаем все строки без табуляции
                tsv_report = 'Имя\tОтвет 1\tОтвет 2\n'
                for line in lines:
                    if '\t' in line:
                        tsv_report += line + '\n'
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8-sig') as f:
                f.write(tsv_report)
            print(f"Отчёт сохранён: {output_file}")
            # --- Графики и дэшборд ---
            import pandas as pd
            import matplotlib.pyplot as plt
            lines = tsv_report.splitlines()
            if len(lines) > 1:
                df = pd.DataFrame([x.split('\t') for x in lines[1:] if x.strip()], columns=lines[0].split('\t'))
                # График распределения мотиваций (Ответ 1)
                motivation_counts = df['Ответ 1'].value_counts().head(15)
                plt.figure(figsize=(10, 6))
                motivation_counts.plot(kind='barh', color='skyblue')
                plt.title('Топ-15 мотиваций прихода в reLove')
                plt.xlabel('Количество')
                plt.ylabel('Мотивация')
                plt.tight_layout()
                plt.savefig('temp/graph_motivation.svg')
                plt.close()
                # График распределения изменений (Ответ 2)
                result_counts = df['Ответ 2'].value_counts().head(15)
                plt.figure(figsize=(10, 6))
                result_counts.plot(kind='barh', color='lightgreen')
                plt.title('Топ-15 изменений после участия')
                plt.xlabel('Количество')
                plt.ylabel('Изменение')
                plt.tight_layout()
                plt.savefig('temp/graph_result.svg')
                plt.close()
                print('Графики сохранены: temp/graph_motivation.svg, temp/graph_result.svg')
                # --- HTML dashboard ---
                dashboard_html = f'''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Аналитика reLove</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; }}
        .graph {{ margin-bottom: 40px; }}
        .report-link {{ margin-top: 30px; display: block; font-size: 1.2em; }}
    </style>
</head>
<body>
    <h1>Аналитика reLove: мотивации и изменения</h1>
    <div class="graph">
        <h2>Топ-15 мотиваций прихода</h2>
        <object type="image/svg+xml" data="graph_motivation.svg" width="800" height="500"></object>
    </div>
    <div class="graph">
        <h2>Топ-15 изменений после участия</h2>
        <object type="image/svg+xml" data="graph_result.svg" width="800" height="500"></object>
    </div>
    <a class="report-link" href="{output_file.name}" target="_blank">Скачать итоговый отчёт (TSV)</a>
</body>
</html>
'''
                with open('temp/dashboard.html', 'w', encoding='utf-8') as f:
                    f.write(dashboard_html)
                print('HTML-дэшборд сохранён: temp/dashboard.html')
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
        MAX_CHARS = 20000  # лимит символов на батч
        def split_batches(messages, max_chars):
            batch = []
            total = 0
            for msg in messages:
                text = msg_text_to_str(msg)
                if total + len(text) > max_chars and batch:
                    yield batch
                    batch = []
                    total = 0
                batch.append(msg)
                total += len(text)
            if batch:
                yield batch
        for user_id, user_messages in users.items():
            all_answers = []
            for batch in split_batches(user_messages, MAX_CHARS):
                user_text = "\n".join([msg_text_to_str(msg) for msg in batch if msg_text_to_str(msg)])
                prompt = (
                    "На основе сообщений пользователя, строго в формате:\n"
                    "1. [ответ на первый вопрос]\n"
                    "2. [ответ на второй вопрос]\n"
                    "Ответ должен содержать только две строки: первая начинается с '1.', вторая — с '2.'. Никаких дополнительных комментариев, тегов, пояснений, пустых строк, markdown или html-разметки быть не должно.\n"
                    "Пример:\n1. Хочу разобраться в себе.\n2. Стал увереннее.\n"
                    "Если не хватает информации — всё равно верни две строки, но максимально лаконично.\n"
                    "Вопросы:\n"
                    "1. Почему человек пришёл в reLove? Опиши его внутреннюю мотивацию или проблему, которая его привела.\n"
                    "2. Какой результат или изменения он/она получил(а) после участия?\n"
                    f"\n\nСообщения пользователя:\n{user_text}"
                )
                analysis = await llm_service.analyze_text(prompt=prompt, system_prompt=None, max_tokens=512)
                all_answers.append(analysis)
            results[user_id] = {"analysis": all_answers, "messages": user_messages}
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
        # Формируем заголовок таблицы
        report = "Имя\tОтвет 1\tОтвет 2\n"
        for user_id, data in results.items():
            if not data['messages']:
                continue
            username = user_info_map.get(user_id, f'Пользователь {user_id}')
            answers = data['analysis']
            q1 = ''
            q2 = ''
            found_q1 = False
            found_q2 = False
            def clean_cell(text):
                # Удаляем html/markdown-теги и все переносы строк
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'[`*_#\[\]()~]', '', text)
                text = text.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
                return ' '.join(text.split())
            def extract(line):
                nonlocal q1, q2, found_q1, found_q2
                if line.startswith('1.') and not found_q1:
                    q1 = clean_cell(line[2:].strip())
                    found_q1 = True
                elif line.startswith('2.') and not found_q2:
                    q2 = clean_cell(line[2:].strip())
                    found_q2 = True
            if isinstance(answers, str):
                for line in answers.splitlines():
                    extract(line.strip())
            elif isinstance(answers, list):
                for answer in answers:
                    if isinstance(answer, str):
                        for line in answer.splitlines():
                            extract(line.strip())
                    elif isinstance(answer, list):
                        for ans in answer:
                            extract(ans.strip())
            username_clean = clean_cell(username)
            q1_clean = clean_cell(q1)
            q2_clean = clean_cell(q2)
            report += f"{username_clean}\t{q1_clean}\t{q2_clean}\n"
        return report


def generate_md_report_with_graphs(tsv_path: str, output_md_path: str):
    """
    Генерирует md-отчёт с двумя SVG-графиками и markdown-таблицей на основе TSV-файла.
    :param tsv_path: путь к TSV-файлу (таблица с колонками Имя, Ответ 1, Ответ 2)
    :param output_md_path: путь для итогового md-файла
    """
    import pandas as pd
    import matplotlib.pyplot as plt
    import io
    # Читаем TSV
    with open(tsv_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines or len(lines) < 2:
        raise ValueError('TSV-файл пуст или не содержит данных')
    df = pd.DataFrame([x.split('\t') for x in lines[1:]], columns=lines[0].split('\t'))
    # График мотиваций
    motivation_counts = df['Ответ 1'].value_counts().head(15)
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    motivation_counts.plot(kind='barh', color='skyblue', ax=ax1)
    ax1.set_title('Топ-15 мотиваций прихода в reLove')
    ax1.set_xlabel('Количество')
    ax1.set_ylabel('Мотивация')
    plt.tight_layout()
    buf1 = io.BytesIO()
    plt.savefig(buf1, format='svg')
    plt.close(fig1)
    buf1.seek(0)
    svg_motivation = buf1.read().decode('utf-8')
    # График изменений
    result_counts = df['Ответ 2'].value_counts().head(15)
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    result_counts.plot(kind='barh', color='lightgreen', ax=ax2)
    ax2.set_title('Топ-15 изменений после участия')
    ax2.set_xlabel('Количество')
    ax2.set_ylabel('Изменение')
    plt.tight_layout()
    buf2 = io.BytesIO()
    plt.savefig(buf2, format='svg')
    plt.close(fig2)
    buf2.seek(0)
    svg_result = buf2.read().decode('utf-8')
    # Markdown-таблица
    def tsv_to_md_table(tsv_lines):
        rows = [line.split('\t') for line in tsv_lines if line.strip()]
        if not rows:
            return ''
        header = '| ' + ' | '.join(rows[0]) + ' |'
        sep = '| ' + ' | '.join(['---'] * len(rows[0])) + ' |'
        body = ['| ' + ' | '.join(row) + ' |' for row in rows[1:]]
        return '\n'.join([header, sep] + body)
    md_table = tsv_to_md_table(lines)
    # Итоговый md-отчёт
    md_report = f"""
# 📊 Аналитика reLove: мотивации и изменения\n\n## Топ-15 мотиваций прихода\n{svg_motivation}\n\n## Топ-15 изменений после участия\n{svg_result}\n\n## Таблица ответов\n{md_table}\n"""
    with open(output_md_path, 'w', encoding='utf-8') as f:
        f.write(md_report)
    print(f'Итоговый md-отчёт сохранён: {output_md_path}')


SHORT_ANALYSIS_PROMPT = (
    "На основе сообщений пользователя, строго в формате:\n"
    "1. [ответ на первый вопрос]\n"
    "2. [ответ на второй вопрос]\n"
    "Ответ должен содержать только две строки: первая начинается с '1.', вторая — с '2.'. Никаких дополнительных комментариев, тегов, пояснений, пустых строк, markdown или html-разметки быть не должно.\n"
    "Пример:\n1. Хочу разобраться в себе.\n2. Стал увереннее.\n"
    "Если не хватает информации — всё равно верни две строки, но максимально лаконично.\n"
    "Вопросы:\n"
    "1. Почему человек пришёл в reLove? Опиши его внутреннюю мотивацию или проблему, которая его привела.\n"
    "2. Какой результат или изменения он/она получил(а) после участия?\n"
    "\n\nСообщения пользователя:\n{user_text}"
)

class ShortAnalyzer:
    """
    Новый лаконичный анализ: две строки, TSV, графики, md-отчёт.
    """
    def __init__(self):
        pass

    async def analyze_chat(self, chat_data):
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
                        if 'text' in x:
                            parts.append(str(x['text']))
                return " ".join(parts)
            return str(t)
        MAX_CHARS = 20000
        def split_batches(messages, max_chars):
            batch = []
            total = 0
            for msg in messages:
                text = msg_text_to_str(msg)
                if total + len(text) > max_chars and batch:
                    yield batch
                    batch = []
                    total = 0
                batch.append(msg)
                total += len(text)
            if batch:
                yield batch
        for user_id, user_messages in users.items():
            all_answers = []
            for batch in split_batches(user_messages, MAX_CHARS):
                user_text = "\n".join([msg_text_to_str(msg) for msg in batch if msg_text_to_str(msg)])
                prompt = SHORT_ANALYSIS_PROMPT.format(user_text=user_text)
                analysis = await llm_service.analyze_text(prompt=prompt, system_prompt=None, max_tokens=512)
                all_answers.append(analysis)
            results[user_id] = {"analysis": all_answers, "messages": user_messages}
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
        report = "Имя\tОтвет 1\tОтвет 2\n"
        STOP_PHRASES = [
            'ОТРАЖЕНИЕ В ЗЕРКАЛЕ', 'АРХИТЕКТУРА ЗАЩИТ', 'ЗЕРКАЛО', 'АНАЛИЗ', 'БЕСПОЩАДНОЕ ЗЕРКАЛО ИСТИНЫ'
        ]
        def clean_cell(text):
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'[`*_#\[\]()~]', '', text)
            text = text.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
            # Фильтрация типовых фраз
            for phrase in STOP_PHRASES:
                if phrase.lower() in text.lower():
                    return ''
            return ' '.join(text.split())
        for user_id, data in results.items():
            if not data['messages']:
                continue
            username = user_info_map.get(user_id, f'Пользователь {user_id}')
            answers = data['analysis']
            q1 = ''
            q2 = ''
            found_q1 = False
            found_q2 = False
            def extract(line):
                nonlocal q1, q2, found_q1, found_q2
                if line.startswith('1.') and not found_q1:
                    q1 = clean_cell(line[2:].strip())
                    found_q1 = True
                elif line.startswith('2.') and not found_q2:
                    q2 = clean_cell(line[2:].strip())
                    found_q2 = True
            if isinstance(answers, str):
                for line in answers.splitlines():
                    extract(line.strip())
            elif isinstance(answers, list):
                for answer in answers:
                    if isinstance(answer, str):
                        for line in answer.splitlines():
                            extract(line.strip())
                    elif isinstance(answer, list):
                        for ans in answer:
                            extract(ans.strip())
            username_clean = clean_cell(username)
            q1_clean = clean_cell(q1)
            q2_clean = clean_cell(q2)
            report += f"{username_clean}\t{q1_clean}\t{q2_clean}\n"
        return report


if __name__ == "__main__":
    # Запускаем асинхронную функцию
    sys.exit(asyncio.run(main()))
