import asyncio
from relove_bot.utils.fill_profiles import refill_streams_for_all_users

if __name__ == "__main__":
    asyncio.run(refill_streams_for_all_users())
