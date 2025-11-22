# 💾 Backups

Эта папка содержит резервные копии базы данных.

## Создание бэкапа

### Через Docker
```bash
# Используйте скрипт
.\scripts\backup_db_docker.ps1
```

### Через Python
```bash
python scripts/backup_database.py
```

## Восстановление из бэкапа

### Из .dump файла
```bash
docker exec -i relove_db pg_restore -U postgres -d relove_bot < backups/backup_YYYYMMDD_HHMMSS.dump
```

### Из .sql файла
```bash
docker exec -i relove_db psql -U postgres -d relove_bot < backups/backup_YYYYMMDD_HHMMSS.sql
```

## Примечание

⚠️ Файлы бэкапов не коммитятся в Git (см. `.gitignore`). Храните их отдельно в безопасном месте.
