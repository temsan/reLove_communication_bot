from apscheduler.schedulers.asyncio import AsyncIOScheduler
from relove_bot.utils.fill_profiles import fill_all_profiles
import logging

def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: fill_all_profiles("YOUR_CHANNEL_ID"), "interval", days=1)
    scheduler.start()
    logging.info("[Scheduler] Запущен fill_all_profiles (раз в сутки)")
