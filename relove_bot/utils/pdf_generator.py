from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from datetime import datetime
from typing import Dict, List, Any
import json

# Используем системный шрифт Arial
FONT_PATH = "C:\\Windows\\Fonts\\arial.ttf"
pdfmetrics.registerFont(TTFont('Arial', FONT_PATH))

def create_pdf_report(data: Dict[str, Any], output_path: str) -> None:
    """
    Создает PDF отчет на основе данных.
    
    Args:
        data: Словарь с данными для отчета
        output_path: Путь для сохранения PDF файла
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # Устанавливаем шрифт
    c.setFont('Arial', 12)
    
    # Заголовок
    c.setFont('Arial', 16)
    c.drawString(50, height - 50, "Отчет по коммуникациям")
    c.setFont('Arial', 12)
    
    # Дата генерации
    c.drawString(50, height - 80, f"Дата генерации: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    # Основная информация
    y = height - 120
    for key, value in data.items():
        if isinstance(value, (str, int, float)):
            c.drawString(50, y, f"{key}: {value}")
            y -= 20
        elif isinstance(value, list):
            c.drawString(50, y, f"{key}:")
            y -= 20
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        c.drawString(70, y, f"{k}: {v}")
                        y -= 20
                else:
                    c.drawString(70, y, str(item))
                    y -= 20
                if y < 50:  # Если достигли конца страницы
                    c.showPage()
                    c.setFont('Arial', 12)
                    y = height - 50
    
    c.save()

def generate_reports() -> None:
    """
    Генерирует два отчета на основе данных из result.json.
    """
    # Путь к файлу с данными
    data_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scripts', 'result.json')
    
    # Создаем директорию для отчетов, если она не существует
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    # Загружаем данные
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Генерируем отчеты
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Отчет 1: Общая статистика
    stats_data = {
        "Общее количество сообщений": len(data.get("messages", [])),
        "Количество уникальных пользователей": len(set(msg.get("user_id") for msg in data.get("messages", []))),
        "Период": f"{data.get('start_date')} - {data.get('end_date')}"
    }
    create_pdf_report(stats_data, os.path.join(reports_dir, f'stats_report_{timestamp}.pdf'))
    
    # Отчет 2: Детальный анализ
    detailed_data = {
        "Период анализа": f"{data.get('start_date')} - {data.get('end_date')}",
        "Статистика по сообщениям": [
            {
                "Тип сообщения": msg.get("type", "Неизвестно"),
                "Время": msg.get("timestamp", "Неизвестно"),
                "Пользователь": msg.get("user_id", "Неизвестно")
            }
            for msg in data.get("messages", [])
        ]
    }
    create_pdf_report(detailed_data, os.path.join(reports_dir, f'detailed_report_{timestamp}.pdf')) 