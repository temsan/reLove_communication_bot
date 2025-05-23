from pyngrok import ngrok
import asyncio
from scripts.dashboard import start_dashboard

async def main():
    # Запускаем ngrok
    public_url = ngrok.connect(8000)
    print(f"Публичный URL: {public_url}")
    
    # Запускаем дэшборд
    await start_dashboard()

if __name__ == "__main__":
    asyncio.run(main())
