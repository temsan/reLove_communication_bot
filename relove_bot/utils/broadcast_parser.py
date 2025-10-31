"""
Утилита для парсинга критериев рассылки.
"""
import re
from typing import Dict, Optional, List, Any
from datetime import datetime

def parse_criteria(criteria: str) -> Dict[str, Any]:
    """
    Парсит строку критериев в словарь фильтров для БД.
    
    Формат: "key1=value1,key2=value2" или "all"
    
    Поддерживаемые критерии:
    - is_active=true/false
    - has_started_journey=true/false
    - has_completed_journey=true/false
    - last_journey_stage=Обычный мир
    - streams=Путь Героя,Прошлые Жизни
    - registered_before=2024-01-01 (дата в формате YYYY-MM-DD)
    - registered_after=2024-01-01
    
    Примеры:
    - "all" -> {}
    - "is_active=true,has_started_journey=true"
    - "streams=Путь Героя,Прошлые Жизни"
    """
    if not criteria or criteria.lower().strip() == "all":
        return {}
    
    filters = {}
    parts = criteria.split(',')
    
    for part in parts:
        part = part.strip()
        if '=' not in part:
            continue
        
        key, value = part.split('=', 1)
        key = key.strip()
        value = value.strip()
        
        # Булевы значения
        if key in ['is_active', 'has_started_journey', 'has_completed_journey']:
            filters[key] = value.lower() in ['true', '1', 'yes', 'да']
        
        # Этап пути героя
        elif key == 'last_journey_stage':
            filters['last_journey_stage'] = value
        
        # Потоки (через запятую)
        elif key == 'streams':
            streams_list = [s.strip() for s in value.split(',') if s.strip()]
            if streams_list:
                filters['streams'] = streams_list
        
        # Даты регистрации
        elif key == 'registered_before':
            try:
                date = datetime.strptime(value, '%Y-%m-%d')
                filters['registered_before'] = date
            except ValueError:
                pass
        
        elif key == 'registered_after':
            try:
                date = datetime.strptime(value, '%Y-%m-%d')
                filters['registered_after'] = date
            except ValueError:
                pass
    
    return filters

