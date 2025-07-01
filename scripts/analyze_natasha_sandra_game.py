import asyncio
from relove_bot.utils.telegram_client import get_client
from relove_bot.services.llm_service import llm_service

CHANNEL_ID = -1002240997881  # ID канала с -100 для Telethon
START_ID = 35013
END_ID = 35125
OUTPUT_FILE = "natasha_sandra_messages.md"

ANALYSIS_PROMPT = (
    "Проанализируй принцип игры Наташи с Сандрой. "
    "Определи правила, цели, роли участников и динамику взаимодействия. "
    "Сформулируй принцип игры кратко и структурированно."
)

async def main():
    client = await get_client()
    await client.connect()
    print(f"Получаю сообщения из канала {CHANNEL_ID} с {START_ID} по {END_ID}...")
    channel = await client.get_entity(CHANNEL_ID)
    messages = []
    async for message in client.iter_messages(channel, min_id=START_ID-1, max_id=END_ID, reverse=True):
        if message.id >= START_ID and message.id <= END_ID and message.text:
            messages.append(message)
    # Сортируем по id по возрастанию
    messages.sort(key=lambda m: m.id)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Сообщения Наташи с Сандрой (для анализа)\n\n")
        for msg in messages:
            if msg.sender and hasattr(msg.sender, 'first_name'):
                name = msg.sender.first_name or ''
                if hasattr(msg.sender, 'last_name') and msg.sender.last_name:
                    name += f" {msg.sender.last_name}"
                if hasattr(msg.sender, 'username') and msg.sender.username:
                    name += f" (@{msg.sender.username})"
                name = name.strip()
            elif hasattr(msg, 'sender_id') and msg.sender_id:
                name = f"User_{msg.sender_id}"
            else:
                name = "Unknown"
            text = msg.text.replace('\n', ' ').replace('  ', ' ')
            f.write(f"- **{name}** | {msg.date.strftime('%Y-%m-%d %H:%M')} | {text}\n")
        f.write(f"\nВсего сообщений: {len(messages)}\n")
    print(f"Markdown-файл сохранён: {OUTPUT_FILE}\nВсего сообщений: {len(messages)}")

if __name__ == "__main__":
    asyncio.run(main()) 