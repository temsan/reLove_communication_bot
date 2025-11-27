#!/usr/bin/env python3
"""
Мониторинг fine-tuning в Colab через Google Drive.
Отслеживает логи и прогресс обучения.
"""

import time
import json
from pathlib import Path
from datetime import datetime
import sys

def monitor_training(drive_path: str = "G:/MyDrive/relove_finetuning", interval: int = 30):
    """
    Мониторит прогресс обучения.
    
    Args:
        drive_path: Путь к Google Drive (например, G:/MyDrive/relove_finetuning)
        interval: Интервал проверки в секундах
    """
    drive_path = Path(drive_path)
    output_dir = drive_path / "model_output"
    stats_file = output_dir / "training_stats.json"
    
    print(f"Monitoring training at: {drive_path}")
    print(f"Checking every {interval} seconds...")
    print("Press Ctrl+C to stop\n")
    
    last_stats = None
    
    try:
        while True:
            if stats_file.exists():
                try:
                    with open(stats_file) as f:
                        stats = json.load(f)
                    
                    if stats != last_stats:
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Training Update:")
                        print(f"  Final Loss: {stats.get('final_loss', 'N/A')}")
                        print(f"  Min Loss: {stats.get('min_loss', 'N/A')}")
                        print(f"  Avg Loss: {stats.get('avg_loss', 'N/A')}")
                        print(f"  Total Steps: {stats.get('total_steps', 'N/A')}")
                        last_stats = stats
                except Exception as e:
                    print(f"Error reading stats: {e}")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for training to start...")
            
            # Проверяем наличие checkpoint'ов
            if output_dir.exists():
                checkpoints = list(output_dir.glob("checkpoint-*"))
                if checkpoints:
                    latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
                    print(f"  Latest checkpoint: {latest.name}")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
        if last_stats:
            print("\nFinal stats:")
            print(json.dumps(last_stats, indent=2))


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor Colab training")
    parser.add_argument(
        '--drive-path',
        type=str,
        default='G:/MyDrive/relove_finetuning',
        help='Path to Google Drive folder'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Check interval in seconds'
    )
    
    args = parser.parse_args()
    monitor_training(args.drive_path, args.interval)
