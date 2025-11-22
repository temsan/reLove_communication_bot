#!/usr/bin/env python3
"""
Скрипт получения и анализа диалога между Тимуром и Сосой из Telegram канала.
Автоматически переавторизуется при необходимости.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Устанавливаем UTF-8 кодировку для Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telethon import TelegramClient
import logging

# Подавляем логи Telethon
logging.getLogger('telethon').setLevel(logging.WARNING)

load_dotenv()

CHANNEL_ID = -1002240997881
TEIMIR_ID = 128809457
SOSA_ID = 1410582771

async def main():
    # Удаляем старую сессию если нужна переавторизация
    session_files = ['relove_bot.session', 'relove_bot.session-journal']
    
    # Загружаем конфиг
    api_id = int(os.getenv('TG_API_ID', '0'))
    api_hash = os.getenv('TG_API_HASH', '')
    
    if not api_id or not api_hash:
        print('❌ TG_API_ID или TG_API_HASH не установлены в .env')
        return
    
    # Создаём клиент
    client = TelegramClient('relove_bot', api_id, api_hash)
    
    try:
        print('⏳ Подключаюсь к Telegram...')
        await client.connect()
        print('✅ Подключено\n')
        
        # Проверяем авторизацию
        if not await client.is_user_authorized():
            print('📱 Требуется авторизация')
            print('Введите номер телефона (с кодом страны, например +7123456789):')
            phone = input('> ')
            
            print('⏳ Отправляю код подтверждения...')
            await client.send_code_request(phone)
            
            print('Введите код из Telegram:')
            code = input('> ')
            
            print('⏳ Авторизуюсь...')
            try:
                await client.sign_in(phone, code)
                print('✅ Авторизация успешна!\n')
            except Exception as e:
                print(f'❌ Ошибка авторизации: {e}')
                return
        
        # Проверяем подключение
        me = await client.get_me()
        print(f'👤 Вы: {me.first_name} (@{me.username})\n')
        
        # Получаем канал
        print('📥 Получаю информацию о канале...')
        channel = await client.get_entity(CHANNEL_ID)
        print(f'✅ Канал: {getattr(channel, "title", CHANNEL_ID)}\n')
        
        # Получаем информацию о пользователях
        print('👤 Получаю информацию о пользователях...')
        try:
            teimir_user = await client.get_entity(TEIMIR_ID)
            teimir_name = f'@{teimir_user.username}' if hasattr(teimir_user, 'username') and teimir_user.username else 'Тимур'
            print(f'✅ Тимур: {teimir_name}')
        except:
            teimir_name = 'Тимур'
        
        try:
            sosa_user = await client.get_entity(SOSA_ID)
            sosa_name = f'@{sosa_user.username}' if hasattr(sosa_user, 'username') and sosa_user.username else 'Соса'
            print(f'✅ Соса: {sosa_name}')
        except:
            sosa_name = 'Соса'
        
        # Получаем сообщения
        print(f'\n📨 Получаю сообщения Тимура...')
        teimir_msgs = []
        count = 0
        async for message in client.iter_messages(channel, from_user=TEIMIR_ID, limit=200):
            if message.text:
                teimir_msgs.append({
                    'id': message.id,
                    'text': message.text,
                    'date': str(message.date)
                })
                count += 1
                if count % 50 == 0:
                    print(f'  ... получено {count}')
        print(f'✅ Получено {len(teimir_msgs)} сообщений Тимура')
        
        print(f'📨 Получаю сообщения Соса...')
        sosa_msgs = []
        count = 0
        async for message in client.iter_messages(channel, from_user=SOSA_ID, limit=200):
            if message.text:
                sosa_msgs.append({
                    'id': message.id,
                    'text': message.text,
                    'date': str(message.date)
                })
                count += 1
                if count % 50 == 0:
                    print(f'  ... получено {count}')
        print(f'✅ Получено {len(sosa_msgs)} сообщений Соса\n')
        
        # Ищем вопрос Тимура
        print('🔍 Ищу вопрос Тимура...')
        question = None
        for msg in teimir_msgs:
            if 'описать' in msg['text'].lower() and 'донести' in msg['text'].lower():
                question = msg['text']
                break
        
        if question:
            print(f'✅ Найден вопрос:\n   "{question}"\n')
            
            # Сохраняем данные
            os.makedirs('temp', exist_ok=True)
            
            export_data = {
                'question': question,
                'teimir_id': TEIMIR_ID,
                'teimir_name': teimir_name,
                'sosa_id': SOSA_ID,
                'sosa_name': sosa_name,
                'channel_id': CHANNEL_ID,
                'teimir_messages': teimir_msgs[-30:],
                'sosa_messages': sosa_msgs[-30:]
            }
            
            export_file = 'temp/timur_sosa_dialog.json'
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print(f'✅ JSON сохранён: {export_file}')
            
            # Текстовый формат
            dialog_text = f"{'='*80}\n"
            dialog_text += f"ДИАЛОГ: {teimir_name} и {sosa_name}\n"
            dialog_text += f"{'='*80}\n\n"
            dialog_text += f"ВОПРОС:\n{question}\n\n"
            dialog_text += f"{'-'*80}\n\n"
            
            dialog_text += f"СООБЩЕНИЯ {teimir_name.upper()}:\n"
            for msg in teimir_msgs[-20:]:
                dialog_text += f"[{msg['date']}]\n{msg['text']}\n\n"
            
            dialog_text += f"{'-'*80}\n\n"
            dialog_text += f"СООБЩЕНИЯ {sosa_name.upper()}:\n"
            for msg in sosa_msgs[-20:]:
                dialog_text += f"[{msg['date']}]\n{msg['text']}\n\n"
            
            dialog_file = 'temp/timur_sosa_dialog.txt'
            with open(dialog_file, 'w', encoding='utf-8') as f:
                f.write(dialog_text)
            
            print(f'✅ TXT сохранён: {dialog_file}\n')
            
            # Анализ LLM
            print('🤖 Пытаюсь подключить LLM...')
            try:
                from relove_bot.services.llm_service import llm_service
                
                teimir_context = teimir_msgs[-20:] if len(teimir_msgs) > 20 else teimir_msgs
                sosa_context = sosa_msgs[-20:] if len(sosa_msgs) > 20 else sosa_msgs
                
                prompt = f"""Ты анализируешь диалог Telegram:
- {teimir_name} (Тимур)
- {sosa_name} (Соса)

Вопрос Тимура: "{question}"

СООБЩЕНИЯ ТИМУРА:
{chr(10).join([f"[{msg['date']}] {msg['text']}" for msg in teimir_context])}

СООБЩЕНИЯ СОСА:
{chr(10).join([f"[{msg['date']}] {msg['text']}" for msg in sosa_context])}

Проанализируй, что Тимур пытается донести Сосе:
1. Главная идея
2. Ключевые моменты
3. Реакция Соса
4. Выводы"""

                analysis = await llm_service.analyze_text(prompt)
                
                print('\n' + '='*80)
                print('📊 АНАЛИЗ:')
                print('='*80 + '\n')
                print(analysis)
                
                analysis_file = 'temp/timur_sosa_analysis.txt'
                with open(analysis_file, 'w', encoding='utf-8') as f:
                    f.write(f"ВОПРОС:\n{question}\n\n{'='*80}\n\n{analysis}")
                print(f'\n✅ Анализ: {analysis_file}')
            except:
                print('⚠️ LLM не доступен')
        else:
            print('❌ Вопрос не найден')
            print('\nПоследние 5 сообщений Тимура:')
            for msg in teimir_msgs[-5:]:
                text = msg['text'][:100].replace('\n', ' ')
                print(f'  [{msg["date"]}] {text}...')
            
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
