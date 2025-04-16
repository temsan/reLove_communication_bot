from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union

from ..config import settings

class IsAdminFilter(BaseFilter):
    """Checks if the user ID is in the admin list from settings."""

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user_id = event.from_user.id
        return user_id in settings.admin_ids 