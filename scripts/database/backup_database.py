#!/usr/bin/env python3
"""Скрипт для создания бекапа базы данных PostgreSQL"""
import os
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем параметры подключения из DB_URL
db_url = os.getenv('DB_URL', 'postgresql+asyncpg://user:pass@localhost:5432/dbname')

# Парсим URL
# Формат: postgresql+asyncpg://user:pass@host:port/dbname
parts = db_url.replace('postgresql+asyncpg://', '').split('@')
user_pass = parts[0].split(':')
host_port_db = parts[1].split('/')
host_port = host_port_db[0].split(':')

db_user = user_pass[0]
db_pass = user_pass[1]
db_host = host_port[0]
db_port = host_port[1] if len(host_port) > 1 else '5432'
db_name = host_port_db[1]

# Создаем имя файла бекапа
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_file = f'backup_{timestamp}.sql'

print(f"Создание бекапа базы данных: {db_name}")
print(f"Хост: {db_host}:{db_port}")
print(f"Пользователь: {db_user}")
print(f"Файл бекапа: {backup_file}")

# Устанавливаем пароль в переменную окружения
env = os.environ.copy()
env['PGPASSWORD'] = db_pass

try:
    # Выполняем pg_dump
    result = subprocess.run(
        [
            'pg_dump',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            '-d', db_name,
            '-f', backup_file,
            '--verbose'
        ],
        env=env,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        file_size = Path(backup_file).stat().st_size
        print(f"\n✓ Бекап успешно создан!")
        print(f"Размер файла: {file_size / 1024:.2f} KB")
        print(f"Путь: {Path(backup_file).absolute()}")
    else:
        print(f"\n✗ Ошибка при создании бекапа:")
        print(result.stderr)
        
except FileNotFoundError:
    print("\n✗ pg_dump не найден. Попробуем альтернативный метод через Python...")
    
    # Альтернативный метод через psycopg2
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_pass,
            database=db_name
        )
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            cursor = conn.cursor()
            
            # Получаем список таблиц
            cursor.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            tables = cursor.fetchall()
            
            f.write(f"-- Бекап базы данных {db_name}\n")
            f.write(f"-- Дата: {datetime.now()}\n")
            f.write(f"-- Хост: {db_host}:{db_port}\n\n")
            f.write("SET client_encoding = 'UTF8';\n")
            f.write("SET standard_conforming_strings = on;\n\n")
            
            total_rows = 0
            for (table_name,) in tables:
                print(f"Обработка таблицы: {table_name}")
                
                # Получаем структуру таблицы
                cursor.execute(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """)
                columns_info = cursor.fetchall()
                columns = [col[0] for col in columns_info]
                
                # Получаем данные
                cursor.execute(f'SELECT * FROM "{table_name}"')
                rows = cursor.fetchall()
                
                f.write(f"\n-- ============================================\n")
                f.write(f"-- Таблица: {table_name}\n")
                f.write(f"-- Колонок: {len(columns)}\n")
                f.write(f"-- Записей: {len(rows)}\n")
                f.write(f"-- ============================================\n\n")
                
                if rows:
                    total_rows += len(rows)
                    columns_str = ', '.join([f'"{col}"' for col in columns])
                    
                    for row in rows:
                        values = []
                        for val in row:
                            if val is None:
                                values.append('NULL')
                            elif isinstance(val, str):
                                # Экранируем одинарные кавычки
                                escaped = val.replace("'", "''").replace('\\', '\\\\')
                                values.append(f"'{escaped}'")
                            elif isinstance(val, (int, float, bool)):
                                values.append(str(val))
                            elif isinstance(val, datetime):
                                values.append(f"'{val.isoformat()}'")
                            else:
                                values.append(f"'{str(val)}'")
                        
                        values_str = ', '.join(values)
                        f.write(f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({values_str});\n')
                    
                    f.write('\n')
            
            cursor.close()
            conn.close()
        
        file_size = Path(backup_file).stat().st_size
        print(f"\n✓ Бекап создан альтернативным методом!")
        print(f"Всего таблиц: {len(tables)}")
        print(f"Всего записей: {total_rows}")
        print(f"Размер файла: {file_size / 1024:.2f} KB ({file_size / (1024*1024):.2f} MB)")
        print(f"Путь: {Path(backup_file).absolute()}")
        
    except ImportError:
        print("✗ psycopg2 не установлен. Установите: pip install psycopg2-binary")
    except Exception as e:
        print(f"✗ Ошибка: {e}")

except Exception as e:
    print(f"\n✗ Неожиданная ошибка: {e}")
