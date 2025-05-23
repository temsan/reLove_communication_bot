import re

# Читаем исходный файл
with open('relove_bot/services/telegram_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Находим начало функции get_personal_channel_id
pattern = r'(async def get_personal_channel_id\(user_id: int\) -> Optional\[int\]:\n\s+"""\n\s+Получает ID личного канала пользователя через GetFullUserRequest \(если привязан\)\.\n\s+"""\n\s+client = await get_client\(\)\n\s+try:\n\s+full_user = await client\(GetFullUserRequest\(user_id\)\)\n\s+pc_id = getattr\(full_user\.full_user, \'personal_channel_id\', None\)\n\s+return pc_id\n\s+)except Exception as e:(\n\s+)'

# Создаем исправленную версию функции
fixed_function = """    client = None
    try:
        client = await get_client()
        full_user = await client(GetFullUserRequest(user_id))
        pc_id = getattr(full_user.full_user, 'personal_channel_id', None)
        if pc_id:
            logger.debug(f"Найден персональный канал {pc_id} для пользователя {user_id}")
        return pc_id
    except Exception as e:
        logger.warning(f"Не удалось получить персональный канал для пользователя {user_id}: {e}")
        return None
    finally:
        if client and client.is_connected():
            await client.disconnect()
"""

# Заменяем старую реализацию на новую
new_content = re.sub(pattern, fixed_function, content, flags=re.DOTALL)

# Сохраняем изменения
with open('relove_bot/services/telegram_service.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Файл успешно обновлен!")
