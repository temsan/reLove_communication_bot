"""
Сервис для массовой рассылки сообщений.
"""

from telethon.errors.rpcerrorlist import PeerFloodError
import asyncio
import logging

class BroadcastService:
    def __init__(self, user_ids):
        self.user_ids = user_ids

    async def send_broadcast(self, text, delay=0.7):
        """
        Рассылает сообщение всем пользователям из списка user_ids.
        """
        sent, failed = 0, 0
        for uid in self.user_ids:
            try:
                await client.send_message(uid, text)
                sent += 1
                # await asyncio.sleep(delay)
            except PeerFloodError:
                logging.warning(f"Flood control for {uid}, skipping...")
                failed += 1
            except Exception as e:
                logging.warning(f"Failed to send to {uid}: {e}")
                failed += 1
        return sent, failed
