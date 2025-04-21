"""
Автоматическое применение миграций Alembic при старте базы.
Можно запускать отдельно или импортировать в другие скрипты.
"""
import os
import subprocess

def run_alembic_upgrade():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_ini = os.path.join(base_dir, 'alembic.ini')
    if os.path.exists(alembic_ini):
        print('[alembic] Применение миграций...')
        result = subprocess.run(['alembic', 'upgrade', 'head'], cwd=base_dir)
        if result.returncode == 0:
            print('[alembic] Миграции успешно применены.')
        else:
            print('[alembic] Ошибка применения миграций!')
    else:
        print('[alembic] alembic.ini не найден — миграции не применялись.')

if __name__ == '__main__':
    run_alembic_upgrade()
