#!/usr/bin/env python3
"""
Анализ качества датасета диалогов Наташи для fine-tuning.

Задачи:
1. Статистика по длине сообщений
2. Анализ распределения по каналам
3. Проверка качества QA пар
4. Выявление аномалий
5. Рекомендации по улучшению
"""
import json
import csv
import sys
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatasetAnalyzer:
    """Анализатор датасета."""
    
    def __init__(self, json_path: str):
        self.json_path = json_path
        self.data = None
        self.dialogs = []
        self.qa_pairs = []
        self.statistics = {}
        
        self._load_data()
    
    def _load_data(self):
        """Загружает данные из JSON."""
        logger.info(f"Loading dataset from {self.json_path}")
        
        with open(self.json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.dialogs = self.data.get('dialogs', [])
        logger.info(f"Loaded {len(self.dialogs)} dialogs")
    
    def analyze_message_lengths(self) -> Dict[str, Any]:
        """Анализирует длину сообщений."""
        logger.info("\n" + "="*70)
        logger.info("MESSAGE LENGTH ANALYSIS")
        logger.info("="*70)
        
        user_lengths = []
        natasha_lengths = []
        
        for dialog in self.dialogs:
            user_msg = dialog.get('user_message', '')
            natasha_msg = dialog.get('natasha_response', '')
            
            if user_msg:
                user_lengths.append(len(user_msg))
            if natasha_msg:
                natasha_lengths.append(len(natasha_msg))
        
        stats = {
            'user_messages': {
                'count': len(user_lengths),
                'min': min(user_lengths) if user_lengths else 0,
                'max': max(user_lengths) if user_lengths else 0,
                'mean': statistics.mean(user_lengths) if user_lengths else 0,
                'median': statistics.median(user_lengths) if user_lengths else 0,
                'stdev': statistics.stdev(user_lengths) if len(user_lengths) > 1 else 0,
            },
            'natasha_messages': {
                'count': len(natasha_lengths),
                'min': min(natasha_lengths) if natasha_lengths else 0,
                'max': max(natasha_lengths) if natasha_lengths else 0,
                'mean': statistics.mean(natasha_lengths) if natasha_lengths else 0,
                'median': statistics.median(natasha_lengths) if natasha_lengths else 0,
                'stdev': statistics.stdev(natasha_lengths) if len(natasha_lengths) > 1 else 0,
            }
        }
        
        logger.info("\nUser Messages:")
        logger.info(f"  Count: {stats['user_messages']['count']}")
        logger.info(f"  Min: {stats['user_messages']['min']} chars")
        logger.info(f"  Max: {stats['user_messages']['max']} chars")
        logger.info(f"  Mean: {stats['user_messages']['mean']:.1f} chars")
        logger.info(f"  Median: {stats['user_messages']['median']} chars")
        logger.info(f"  Stdev: {stats['user_messages']['stdev']:.1f}")
        
        logger.info("\nNatasha Messages:")
        logger.info(f"  Count: {stats['natasha_messages']['count']}")
        logger.info(f"  Min: {stats['natasha_messages']['min']} chars")
        logger.info(f"  Max: {stats['natasha_messages']['max']} chars")
        logger.info(f"  Mean: {stats['natasha_messages']['mean']:.1f} chars")
        logger.info(f"  Median: {stats['natasha_messages']['median']} chars")
        logger.info(f"  Stdev: {stats['natasha_messages']['stdev']:.1f}")
        
        self.statistics['message_lengths'] = stats
        return stats
    
    def analyze_channel_distribution(self) -> Dict[str, int]:
        """Анализирует распределение по каналам."""
        logger.info("\n" + "="*70)
        logger.info("CHANNEL DISTRIBUTION")
        logger.info("="*70)
        
        channel_counts = defaultdict(int)
        
        for dialog in self.dialogs:
            channel = dialog.get('channel', 'Unknown')
            channel_counts[channel] += 1
        
        # Сортируем по количеству
        sorted_channels = sorted(
            channel_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        logger.info(f"\nTotal channels: {len(sorted_channels)}")
        logger.info("\nTop channels:")
        
        for i, (channel, count) in enumerate(sorted_channels[:10], 1):
            percentage = (count / len(self.dialogs)) * 100
            logger.info(f"  {i}. {channel}: {count} dialogs ({percentage:.1f}%)")
        
        if len(sorted_channels) > 10:
            logger.info(f"  ... and {len(sorted_channels) - 10} more channels")
        
        self.statistics['channel_distribution'] = dict(sorted_channels)
        return dict(sorted_channels)
    
    def analyze_dialog_types(self) -> Dict[str, int]:
        """Анализирует типы диалогов."""
        logger.info("\n" + "="*70)
        logger.info("DIALOG TYPES")
        logger.info("="*70)
        
        type_counts = defaultdict(int)
        
        for dialog in self.dialogs:
            dialog_type = dialog.get('type', 'unknown')
            type_counts[dialog_type] += 1
        
        logger.info("\nDialog types:")
        for dialog_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(self.dialogs)) * 100
            logger.info(f"  {dialog_type}: {count} ({percentage:.1f}%)")
        
        self.statistics['dialog_types'] = dict(type_counts)
        return dict(type_counts)
    
    def analyze_quality_metrics(self) -> Dict[str, Any]:
        """Анализирует метрики качества."""
        logger.info("\n" + "="*70)
        logger.info("QUALITY METRICS")
        logger.info("="*70)
        
        metrics = {
            'total_dialogs': len(self.dialogs),
            'dialogs_with_context': 0,
            'dialogs_with_reply_chain': 0,
            'avg_context_length': 0,
            'quality_issues': []
        }
        
        context_lengths = []
        
        for dialog in self.dialogs:
            context = dialog.get('context', [])
            if context:
                metrics['dialogs_with_context'] += 1
                context_lengths.append(len(context))
            
            if dialog.get('type') == 'reply_chain':
                metrics['dialogs_with_reply_chain'] += 1
            
            # Проверяем качество
            user_msg = dialog.get('user_message', '')
            natasha_msg = dialog.get('natasha_response', '')
            
            # Слишком короткие сообщения
            if len(user_msg) < 30:
                metrics['quality_issues'].append({
                    'type': 'short_user_message',
                    'channel': dialog.get('channel'),
                    'length': len(user_msg)
                })
            
            if len(natasha_msg) < 20:
                metrics['quality_issues'].append({
                    'type': 'short_natasha_message',
                    'channel': dialog.get('channel'),
                    'length': len(natasha_msg)
                })
        
        if context_lengths:
            metrics['avg_context_length'] = statistics.mean(context_lengths)
        
        logger.info(f"\nTotal dialogs: {metrics['total_dialogs']}")
        logger.info(f"Dialogs with context: {metrics['dialogs_with_context']} ({(metrics['dialogs_with_context']/metrics['total_dialogs']*100):.1f}%)")
        logger.info(f"Dialogs with reply chain: {metrics['dialogs_with_reply_chain']} ({(metrics['dialogs_with_reply_chain']/metrics['total_dialogs']*100):.1f}%)")
        logger.info(f"Average context length: {metrics['avg_context_length']:.1f} messages")
        
        # Качество
        logger.info(f"\nQuality issues found: {len(metrics['quality_issues'])}")
        
        issue_types = defaultdict(int)
        for issue in metrics['quality_issues']:
            issue_types[issue['type']] += 1
        
        for issue_type, count in issue_types.items():
            logger.info(f"  {issue_type}: {count}")
        
        self.statistics['quality_metrics'] = metrics
        return metrics
    
    def analyze_content_themes(self) -> Dict[str, int]:
        """Анализирует темы контента."""
        logger.info("\n" + "="*70)
        logger.info("CONTENT THEMES")
        logger.info("="*70)
        
        themes = {
            'spiritual_growth': 0,
            'past_lives': 0,
            'rituals': 0,
            'relationships': 0,
            'business': 0,
            'personal_transformation': 0,
            'energy_work': 0,
            'questions': 0
        }
        
        keywords = {
            'spiritual_growth': ['путь', 'развитие', 'трансформация', 'осознание', 'прозрение'],
            'past_lives': ['прошлая жизнь', 'инкарнация', 'воплощение', 'ПЖ', 'жизнь'],
            'rituals': ['ритуал', 'медитация', 'практика', 'мистерия'],
            'relationships': ['отношение', 'мужчина', 'женщина', 'любовь', 'партнер'],
            'business': ['бизнес', 'проект', 'продажи', 'маркетинг', 'творчество'],
            'personal_transformation': ['изменение', 'стал', 'стала', 'изменилась', 'преодолел'],
            'energy_work': ['энергия', 'вибрация', 'центр', 'поток', 'пространство'],
            'questions': ['?']
        }
        
        for dialog in self.dialogs:
            natasha_msg = dialog.get('natasha_response', '').lower()
            user_msg = dialog.get('user_message', '').lower()
            combined = natasha_msg + ' ' + user_msg
            
            for theme, keywords_list in keywords.items():
                if any(kw in combined for kw in keywords_list):
                    themes[theme] += 1
        
        logger.info("\nContent themes:")
        for theme, count in sorted(themes.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(self.dialogs)) * 100
            logger.info(f"  {theme}: {count} ({percentage:.1f}%)")
        
        self.statistics['content_themes'] = themes
        return themes
    
    def generate_recommendations(self) -> List[str]:
        """Генерирует рекомендации."""
        logger.info("\n" + "="*70)
        logger.info("RECOMMENDATIONS")
        logger.info("="*70)
        
        recommendations = []
        
        # Проверяем размер датасета
        if len(self.dialogs) < 100:
            recommendations.append("⚠️  Датасет содержит менее 100 диалогов. Рекомендуется собрать больше данных для лучшего fine-tuning.")
        elif len(self.dialogs) < 500:
            recommendations.append("✓ Датасет содержит достаточно данных для базового fine-tuning (100-500 примеров).")
        else:
            recommendations.append("✓ Датасет содержит много данных для качественного fine-tuning (500+ примеров).")
        
        # Проверяем распределение по каналам
        channel_dist = self.statistics.get('channel_distribution', {})
        if channel_dist:
            max_channel_count = max(channel_dist.values())
            max_percentage = (max_channel_count / len(self.dialogs)) * 100
            
            if max_percentage > 50:
                recommendations.append(f"⚠️  Один канал содержит {max_percentage:.1f}% данных. Рекомендуется балансировать данные из разных каналов.")
            else:
                recommendations.append("✓ Данные хорошо распределены по каналам.")
        
        # Проверяем длину сообщений
        msg_lengths = self.statistics.get('message_lengths', {})
        if msg_lengths:
            natasha_mean = msg_lengths.get('natasha_messages', {}).get('mean', 0)
            
            if natasha_mean < 50:
                recommendations.append("⚠️  Средняя длина ответов Наташи менее 50 символов. Это может привести к коротким ответам модели.")
            elif natasha_mean > 500:
                recommendations.append("✓ Средняя длина ответов оптимальна для fine-tuning.")
        
        # Проверяем качество
        quality = self.statistics.get('quality_metrics', {})
        if quality:
            issues = quality.get('quality_issues', [])
            if len(issues) > len(self.dialogs) * 0.1:
                recommendations.append(f"⚠️  Найдено {len(issues)} проблем с качеством ({len(issues)/len(self.dialogs)*100:.1f}%). Рекомендуется проверить данные.")
            else:
                recommendations.append("✓ Качество данных хорошее.")
        
        # Рекомендации по fine-tuning
        recommendations.append("\n📚 Рекомендации по fine-tuning:")
        recommendations.append("  1. Используйте JSONL файл (natasha_finetuning_*.jsonl)")
        recommendations.append("  2. Начните с 3 эпох обучения")
        recommendations.append("  3. Используйте learning_rate_multiplier = 0.1")
        recommendations.append("  4. Тестируйте на примерах из разных каналов")
        recommendations.append("  5. Комбинируйте с другими датасетами для универсальности")
        
        for rec in recommendations:
            logger.info(rec)
        
        return recommendations
    
    def save_analysis_report(self, output_path: str = None):
        """Сохраняет отчет анализа."""
        if not output_path:
            output_path = f"data/dataset_analysis_{Path(self.json_path).stem}.json"
        
        report = {
            'dataset_file': self.json_path,
            'statistics': self.statistics
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n✅ Analysis report saved to: {output_path}")
        return output_path
    
    def run_full_analysis(self):
        """Запускает полный анализ."""
        logger.info("\n" + "="*70)
        logger.info("NATASHA DATASET ANALYSIS")
        logger.info("="*70)
        
        self.analyze_message_lengths()
        self.analyze_channel_distribution()
        self.analyze_dialog_types()
        self.analyze_quality_metrics()
        self.analyze_content_themes()
        self.generate_recommendations()
        
        self.save_analysis_report()
        
        logger.info("\n" + "="*70)
        logger.info("ANALYSIS COMPLETE")
        logger.info("="*70 + "\n")


def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze Natasha's dialogs dataset"
    )
    parser.add_argument(
        '--input',
        type=str,
        default='data/natasha_dialogs_dataset_20251125_153356.json',
        help='Input JSON file with dialogs'
    )
    
    args = parser.parse_args()
    
    if not Path(args.input).exists():
        logger.error(f"File not found: {args.input}")
        return
    
    analyzer = DatasetAnalyzer(args.input)
    analyzer.run_full_analysis()


if __name__ == "__main__":
    main()
