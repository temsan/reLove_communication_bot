# Скрипт для создания бекапа PostgreSQL из Docker контейнера
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupFile = "backup_$timestamp.dump"

Write-Host "Создание бекапа базы данных из Docker контейнера..." -ForegroundColor Cyan
Write-Host "Контейнер: relove_postgres" -ForegroundColor Gray
Write-Host "База данных: dbname" -ForegroundColor Gray
Write-Host "Формат: Custom (сжатый бинарный)" -ForegroundColor Gray
Write-Host "Файл: $backupFile" -ForegroundColor Gray
Write-Host ""

# Создаем бекап в custom формате внутри контейнера, затем копируем
docker exec relove_postgres pg_dump -U user -d dbname -F c -f /tmp/backup.dump
docker cp relove_postgres:/tmp/backup.dump $backupFile
docker exec relove_postgres rm /tmp/backup.dump

if ($LASTEXITCODE -eq 0) {
    $fileSize = (Get-Item $backupFile).Length
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    
    Write-Host "✓ Бекап успешно создан!" -ForegroundColor Green
    Write-Host "  Размер: $fileSizeMB MB" -ForegroundColor Green
    Write-Host "  Путь: $((Get-Item $backupFile).FullName)" -ForegroundColor Green
} else {
    Write-Host "✗ Ошибка при создании бекапа" -ForegroundColor Red
}
