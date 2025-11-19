import asyncio
import sys
import logging

# Настройка логирования для отладки
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("🚀 Starting bot initialization...", flush=True)

try:
    from .bot import main
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}", flush=True)
    sys.exit(1)

if __name__ == "__main__":
    try:
        print("▶️  Running main()...", flush=True)
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        sys.exit(0)
    except SystemExit as e:
        if e.code != 0:
            print(f"❌ Bot exited with code {e.code}")
        sys.exit(e.code)
    except Exception as e:
        error_msg = str(e).lower()
        
        if "connection refused" in error_msg or "refused" in error_msg:
            print(
                "\n❌ БД недоступна!\n"
                "Убедитесь, что Docker контейнеры запущены:\n"
                "   docker-compose up -d\n"
                f"Ошибка: {e}",
                flush=True
            )
        else:
            print(f"\n❌ Unexpected error: {e}", flush=True)
            import traceback
            traceback.print_exc()
        
        sys.exit(1)
