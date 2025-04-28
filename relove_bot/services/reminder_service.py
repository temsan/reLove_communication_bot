"""
Сервис напоминаний пользователям.
"""
import asyncio
import logging

class ReminderService:
    def __init__(self):
        self.tasks = []

    async def schedule_reminder(self, user_id, text, when):
        """
        Планирует отправку напоминания пользователю (when — datetime).
        """
        now = asyncio.get_event_loop().time()
        delay = (when - now)
        if delay < 0:
            delay = 0
        task = asyncio.create_task(self._remind_later(user_id, text, delay))
        self.tasks.append(task)
        return task

    async def _remind_later(self, user_id, text, delay):
        await asyncio.sleep(delay)
        try:
            await client.send_message(user_id, text)
        except Exception as e:
            logging.warning(f"Не удалось отправить напоминание {user_id}: {e}")
