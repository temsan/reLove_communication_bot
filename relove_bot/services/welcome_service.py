"""
Сервис приветственных сообщений новым участникам.
"""

import logging

WELCOME_TEMPLATE = (
    "Добро пожаловать в наше сообщество!\n"
    "\n"
    "Пожалуйста, ознакомьтесь с правилами и заполните свой профиль.\n"
    "Если возникнут вопросы — пишите администратору."
)

class WelcomeService:
    @staticmethod
    async def send_welcome(user_id, custom_text=None):
        text = custom_text or WELCOME_TEMPLATE
        try:
            await client.send_message(user_id, text)
            return True
        except Exception as e:
            logging.warning(f"Не удалось отправить приветствие {user_id}: {e}")
            return False
