import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from datetime import datetime, timedelta, timezone
from tqdm import tqdm

async def count_subscriptions(client, max_dialogs=3000, inactive_days=180):
    print("Считаю только подписки на каналы и группы...")
    channels = []
    groups = []
    processed = 0
    old_inactive = []
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=inactive_days)
    me = await client.get_me()
    # Сначала считаем общее количество диалогов для корректного прогресс-бара
    print("Получаю общее количество диалогов...")
    total_dialogs = 0
    async for _ in client.iter_dialogs():
        total_dialogs += 1
        if total_dialogs >= max_dialogs:
            break
    print(f"Всего диалогов для обработки: {total_dialogs}")
    try:
        with tqdm(total=total_dialogs, desc="Обработка подписок") as pbar:
            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                # Канал (Channel, megagroup=False)
                if isinstance(entity, Channel) and not getattr(entity, 'megagroup', False):
                    last_message = await client.get_messages(dialog, limit=1)
                    last_msg_date = last_message[0].date if last_message else None
                    if last_msg_date and last_msg_date.astimezone(timezone.utc) < threshold:
                        old_inactive.append({
                            'title': entity.title,
                            'username': getattr(entity, 'username', None),
                            'type': 'channel',
                            'last_msg_date': last_msg_date.strftime('%Y-%m-%d'),
                        })
                    channels.append({'title': entity.title, 'username': getattr(entity, 'username', None)})
                # Группа (Channel, megagroup=True) или Chat с participants_count > 1
                elif (isinstance(entity, Channel) and getattr(entity, 'megagroup', False)) or (isinstance(entity, Chat) and hasattr(entity, 'participants_count') and entity.participants_count > 1):
                    last_message = await client.get_messages(dialog, limit=1)
                    last_msg_date = last_message[0].date if last_message else None
                    my_msgs = await client.get_messages(dialog, from_user=me.id, limit=1)
                    wrote = bool(my_msgs)
                    if (not wrote) and last_msg_date and last_msg_date.astimezone(timezone.utc) < threshold:
                        old_inactive.append({
                            'title': entity.title,
                            'username': getattr(entity, 'username', None),
                            'type': 'group',
                            'last_msg_date': last_msg_date.strftime('%Y-%m-%d'),
                        })
                    groups.append({'title': entity.title, 'username': getattr(entity, 'username', None)})
                processed += 1
                pbar.update(1)
                if processed >= max_dialogs:
                    print(f"Достигнут лимит {max_dialogs} диалогов для диагностики.")
                    break
    except Exception as e:
        print(f"Ошибка при обработке диалогов: {e}")
        return
    print(f"\nСтарые и неактивные подписки:")
    print(f"(Каналы — только по дате, группы — по дате и отсутствию ваших сообщений)")
    print(f"Найдено: {len(old_inactive)}")
    for i, ch in enumerate(old_inactive, 1):
        print(f"{i}. {ch['title']} (@{ch['username']}) - {ch['type']} | последнее сообщение: {ch['last_msg_date']}")
    print("\nВсего каналов: ", len(channels))
    print("Всего групп: ", len(groups))
    print("Всего подписок (каналы + группы): ", len(channels) + len(groups))

async def delete_groups_no_messages_no_reads(client, max_delete=50):
    print(f"Ищу группы, где вы ни разу не писали и не читали... (максимум {max_delete} на удаление)")
    me = await client.get_me()
    groups_to_delete = []
    processed = 0
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        # Только группы (Channel с megagroup=True или Chat с participants_count > 1)
        if (isinstance(entity, Channel) and getattr(entity, 'megagroup', False)) or (isinstance(entity, Chat) and hasattr(entity, 'participants_count') and entity.participants_count > 1):
            my_msgs = await client.get_messages(dialog, from_user=me.id, limit=1)
            # unread_count > 0 — есть непрочитанные, значит не читали
            if not my_msgs and dialog.unread_count > 0:
                groups_to_delete.append({
                    'title': entity.title,
                    'username': getattr(entity, 'username', None),
                    'id': entity.id,
                    'type': 'group',
                })
            if len(groups_to_delete) >= max_delete:
                break
        processed += 1
    print(f"\nГруппы, где вы ни разу не писали и не читали (будут удалены, максимум {max_delete}): {len(groups_to_delete)}")
    for i, gr in enumerate(groups_to_delete, 1):
        print(f"{i}. {gr['title']} (@{gr['username']})")
    # Удаляем
    deleted = 0
    for gr in groups_to_delete:
        try:
            if gr['username']:
                entity = await client.get_entity(gr['username'])
            else:
                entity = gr['id']
            await client.delete_dialog(entity)
            print(f"Удалено: {gr['title']} (@{gr['username']})")
            deleted += 1
        except Exception as e:
            print(f"Ошибка при удалении {gr['title']}: {e}")
    print(f"\nИтого удалено групп: {deleted}")

async def main():
    load_dotenv()
    api_id = int(os.getenv('TG_API_ID'))
    api_hash = os.getenv('TG_API_HASH')
    session_name = os.getenv('TG_SESSION')
    try:
        async with TelegramClient(session_name, api_id, api_hash) as client:
            await count_subscriptions(client, max_dialogs=3000, inactive_days=180)
            await delete_groups_no_messages_no_reads(client, max_delete=50)
    except Exception as e:
        print(f"Ошибка соединения с Telegram: {e}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
