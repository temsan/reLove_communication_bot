import asyncio
import sys
import os
import json
from pathlib import Path

# Устанавливаем UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

# Загружаем .env
from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient

CHANNEL_ID = -1002240997881
TEIMIR_ID = 128809457
SOSA_ID = 1410582771

async def main():
    # Удаляем старые сессии
    for session_file in ['relove_bot.session', 'relove_bot.session-journal']:
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                print(f'🗑️ Удалена сессия: {session_file}')
            except:
                pass
    
    # Создаём новый клиент
    api_id = int(os.getenv('TG_API_ID'))
    api_hash = os.getenv('TG_API_HASH')
    
    client = TelegramClient(
        'relove_bot',
        api_id,
        api_hash,
    )
    
    try:
        print('⏳ Подключаюсь к Telegram...')
        await client.connect()
        
        # Проверяем авторизацию
        if not await client.is_user_authorized():
            print('❌ Необходима авторизация. Используйте bot token из .env')
            return
        
        print('✅ Клиент подключен и авторизован\n')
        
        # Получаем канал
        print('📥 Получаю информацию о канале...')
        try:
            channel = await client.get_entity(CHANNEL_ID)
            print(f'✅ Канал: {channel.title if hasattr(channel, "title") else CHANNEL_ID}')
        except Exception as e:
            print(f'⚠️ Ошибка при получении канала: {e}')
            print(f'Используем ID напрямую: {CHANNEL_ID}')
            channel = CHANNEL_ID
        
        # Получаем информацию о пользователях
        print('\n📨 Получаю информацию о пользователях...')
        try:
            teimir = await client.get_entity(TEIMIR_ID)
            print(f'✅ Тимур найден: {teimir.first_name if hasattr(teimir, "first_name") else ""} (@{teimir.username})')
        except:
            print(f'⚠️ Тимур (ID: {TEIMIR_ID}) не найден')
        
        try:
            sosa = await client.get_entity(SOSA_ID)
            print(f'✅ Соса найден: {sosa.first_name if hasattr(sosa, "first_name") else ""} (@{sosa.username})')
        except:
            print(f'⚠️ Соса (ID: {SOSA_ID}) не найден')
        
        # Получаем сообщения
        print(f'\n📨 Получаю сообщения Тимура из канала...')
        teimir_msgs = []
        count = 0
        try:
            async for msg in client.iter_messages(channel, from_user=TEIMIR_ID, limit=200):
                if msg.text:
                    teimir_msgs.append({
                        'id': msg.id,
                        'text': msg.text,
                        'date': str(msg.date)
                    })
                    count += 1
                    if count % 50 == 0:
                        print(f'  ... получено {count}')
        except Exception as e:
            print(f'⚠️ Ошибка: {e}')
        
        print(f'✅ Получено {len(teimir_msgs)} сообщений Тимура\n')
        
        print(f'📨 Получаю сообщения Соса из канала...')
        sosa_msgs = []
        count = 0
        try:
            async for msg in client.iter_messages(channel, from_user=SOSA_ID, limit=200):
                if msg.text:
                    sosa_msgs.append({
                        'id': msg.id,
                        'text': msg.text,
                        'date': str(msg.date)
                    })
                    count += 1
                    if count % 50 == 0:
                        print(f'  ... получено {count}')
        except Exception as e:
            print(f'⚠️ Ошибка: {e}')
        
        print(f'✅ Получено {len(sosa_msgs)} сообщений Соса\n')
        
        if teimir_msgs or sosa_msgs:
            # Ищем вопрос
            print('🔍 Ищу вопрос Тимура...')
            question = None
            for msg in teimir_msgs:
                text = msg['text'].lower()
                if ('описать' in text and 'донести' in text) or ('help' in text.lower() and 'explain' in text.lower()):
                    question = msg['text']
                    break
            
            if question:
                print(f'✅ Найден вопрос!\n   "{question}"\n')
            else:
                print('ℹ️ Вопрос с ключевыми словами не найден')
                print('   Последние 3 сообщения Тимура:')
                for msg in teimir_msgs[-3:]:
                    print(f'   - {msg["text"][:80]}...')
            
            # Сохраняем данные
            os.makedirs('temp', exist_ok=True)
            
            export_data = {
                'question': question,
                'teimir_id': TEIMIR_ID,
                'sosa_id': SOSA_ID,
                'channel_id': CHANNEL_ID,
                'teimir_messages_count': len(teimir_msgs),
                'sosa_messages_count': len(sosa_msgs),
                'teimir_messages': teimir_msgs[-30:],  # Последние 30
                'sosa_messages': sosa_msgs[-30:],      # Последние 30
            }
            
            export_file = 'temp/timur_sosa_dialog.json'
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print(f'\n✅ Данные сохранены в: {export_file}')
            print(f'\n📊 Статистика:')
            print(f'   Сообщений Тимура: {len(teimir_msgs)}')
            print(f'   Сообщений Соса: {len(sosa_msgs)}')
            print(f'   Сохранено последних: 30 сообщений каждого')
        else:
            print('❌ Не удалось получить сообщения')
        
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
