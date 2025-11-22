# План чистки проекта

## 1. Дублирование функций

### get_user() - 6 дубликатов
- `relove_bot/db/repository.py`
- `relove_bot/db/repository/__init__.py` 
- `relove_bot/db/repository/user_repository.py`
- `relove_bot/services/journey_service.py`
- `relove_bot/utils/fill_profiles.py`

**Решение:** Оставить только в `user_repository.py`, остальные использовать через него

### get_user_streams() - 3 дубликата
- `relove_bot/utils/relove_streams.py`
- `relove_bot/utils/interests.py`
- `relove_bot/services/profile_service.py`

**Решение:** Объединить в `profile_enrichment.py`

### get_user_posts() - 3 дубликата
- `relove_bot/services/telegram_service.py`
- `relove_bot/services/profile_service.py`
- `relove_bot/services/profile_rotation_service.py`

**Решение:** Оставить только в `telegram_service.py`

---

## 2. Мусор в корне

### Переместить в docs/
- CLEANUP_REPORT.md
- IMPLEMENTATION_COMPLETE.md
- INCREMENTAL_UPDATE_GUIDE.md
- INTEGRATION_COMPLETE_REPORT.md
- NATASHA_ANALYSIS_COMPLETE.md
- NATASHA_EXTRACTION_REPORT.md
- NATASHA_STYLE_INTEGRATION.md
- PROFILE_ENRICHMENT_GUIDE.md
- PROFILE_ENRICHMENT_LOGIC.md
- PROFILE_FIELDS_ANALYSIS.md
- PROFILE_REFILL_GUIDE.md
- PROFILE_SYSTEM_SUMMARY.md
- USER_UPDATE_FINAL_REPORT.md

### Удалить устаревшие
- import_users_now.bat (старый скрипт)
- relove_bot.session (сессия Telethon - в .gitignore)

---

## 3. Дублирование repository

### Проблема
- `relove_bot/db/repository.py` (старый)
- `relove_bot/db/repository/__init__.py` (дубликат)
- `relove_bot/db/repository/user_repository.py` (новый)

**Решение:** Удалить старые, оставить только структуру:
```
relove_bot/db/repository/
  __init__.py (экспорты)
  user_repository.py
  session_repository.py
  diagnostic_repository.py
  test_repository.py
```

---

## 4. Устаревшие utils

### relove_bot/utils/
- `fill_profiles.py` - заменён на `scripts/profiles/fill_profiles_from_channels.py`
- `profile_summary.py` - дублирует `profile_service.py`
- `interests.py` - дублирует `profile_enrichment.py`

**Решение:** Удалить, функционал перенесён

---

## 5. Неиспользуемые папки

- `rasa_bot/` - старый бот на Rasa
- `reLoveReason/` - неизвестно
- `telethon_src/` - исходники Telethon?
- `temp/` - временные файлы

**Решение:** Проверить и удалить или переместить в archive/
