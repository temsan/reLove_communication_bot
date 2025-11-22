"""
Демонстрация обновления 5 пользователей из канала с наглядным сравнением ДО/ПОСЛЕ.
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from telethon import TelegramClient
from relove_bot.config import settings
from relove_bot.db.session import get_session
from relove_bot.db.models import User, GenderEnum
from scripts.profiles.fill_profiles_from_channels import ChannelProfileFiller
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/update_5_users_demo.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class UserUpdateDemo:
    """Демонстрация обновления пользователей."""
    
    def __init__(self):
        self.client = TelegramClient(
            settings.tg_session,
            settings.tg_api_id,
            settings.tg_api_hash.get_secret_value()
        )
        self.filler = ChannelProfileFiller()
    
    async def get_5_users_from_channel(self, channel_name: str = "Прошлые Жизни reLove") -> List[Dict[str, Any]]:
        """Получает 5 пользователей из канала."""
        logger.info(f"Getting 5 users from channel: {channel_name}")
        
        users = []
        
        try:
            # Получаем канал
            async for dialog in self.client.iter_dialogs():
                if channel_name.lower() in dialog.name.lower():
                    logger.info(f"Found channel: {dialog.name}")
                    
                    # Получаем участников
                    async for participant in self.client.iter_participants(dialog.entity, limit=100):
                        if participant.bot:
                            continue
                        
                        if len(users) >= 5:
                            break
                        
                        # Собираем данные
                        user_data = {
                            'telegram_id': participant.id,
                            'username': participant.username or '',
                            'first_name': participant.first_name or '',
                            'last_name': participant.last_name or '',
                            'phone': participant.phone or '',
                        }
                        
                        users.append(user_data)
                        logger.info(f"  {len(users)}. {user_data['first_name']} {user_data['last_name']} (@{user_data['username']})")
                    
                    break
        
        except Exception as e:
            logger.error(f"Error getting users: {e}")
        
        return users
    
    async def update_user_in_db(self, user_data: Dict[str, Any]):
        """Обновляет/создаёт пользователя в БД и заполняет пустые поля."""
        async with get_session() as session:
            telegram_id = user_data['telegram_id']
            
            # Проверяем, есть ли пользователь
            result = await session.execute(
                select(User).where(User.id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Обновляем базовые поля
                user.username = user_data.get('username')
                user.first_name = user_data.get('first_name')
                user.last_name = user_data.get('last_name')
                logger.info(f"  ♻️ Updating existing user {telegram_id}")
                
                # Проверяем, нужно ли заполнить профиль
                needs_profile_fill = False
                
                if not user.psychological_summary:
                    logger.info(f"    📝 psychological_summary пуст - нужно заполнить")
                    needs_profile_fill = True
                
                if not user.profile_summary:
                    logger.info(f"    📝 profile_summary пуст - нужно заполнить")
                    needs_profile_fill = True
                
                if needs_profile_fill:
                    # Коммитим базовые изменения
                    await session.commit()
                    
                    # Заполняем профиль через filler
                    logger.info(f"    🔄 Запускаем заполнение профиля...")
                    await self.filler.fill_user_profile(user, session)
                    logger.info(f"    ✅ Профиль заполнен")
            else:
                # Создаём нового
                user = User(
                    id=telegram_id,
                    username=user_data.get('username'),
                    first_name=user_data.get('first_name'),
                    last_name=user_data.get('last_name'),
                    gender=GenderEnum.FEMALE  # По умолчанию female для reLove
                )
                session.add(user)
                logger.info(f"  🆕 Creating new user {telegram_id}")
                
                # Коммитим создание
                await session.commit()
                
                # Заполняем профиль
                logger.info(f"    🔄 Запускаем заполнение профиля для нового пользователя...")
                await self.filler.fill_user_profile(user, session)
                logger.info(f"    ✅ Профиль заполнен")
            
            await session.commit()
    
    async def get_user_state_from_db(self, telegram_id: int) -> Dict[str, Any]:
        """Получает текущее состояние пользователя из БД."""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {
                    'exists': False,
                    'telegram_id': telegram_id,
                }
            
            return {
                'exists': True,
                'telegram_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'gender': user.gender.value if user.gender else None,
                'streams': user.streams or [],
                'profile_summary': user.profile_summary[:100] + '...' if user.profile_summary and len(user.profile_summary) > 100 else user.profile_summary,
                'psychological_summary': user.psychological_summary[:100] + '...' if user.psychological_summary and len(user.psychological_summary) > 100 else user.psychological_summary,
                'registration_date': user.registration_date.isoformat() if user.registration_date else None,
                'last_seen_date': user.last_seen_date.isoformat() if user.last_seen_date else None,
            }
    
    def print_user_comparison(self, before: Dict[str, Any], after: Dict[str, Any], index: int):
        """Выводит сравнение пользователя ДО/ПОСЛЕ."""
        print("\n" + "="*80)
        print(f"ПОЛЬЗОВАТЕЛЬ #{index}")
        print("="*80)
        
        # Имя
        name_before = f"{before.get('first_name', '')} {before.get('last_name', '')}".strip() or "N/A"
        name_after = f"{after.get('first_name', '')} {after.get('last_name', '')}".strip() or "N/A"
        
        print(f"\n📛 ИМЯ:")
        print(f"  ДО:    {name_before}")
        print(f"  ПОСЛЕ: {name_after}")
        if name_before != name_after:
            print("  ✅ ОБНОВЛЕНО")
        
        # Username
        username_before = before.get('username') or "N/A"
        username_after = after.get('username') or "N/A"
        
        print(f"\n👤 USERNAME:")
        print(f"  ДО:    @{username_before}")
        print(f"  ПОСЛЕ: @{username_after}")
        if username_before != username_after:
            print("  ✅ ОБНОВЛЕНО")
        
        # Пол
        gender_before = before.get('gender') or "N/A"
        gender_after = after.get('gender') or "N/A"
        
        print(f"\n⚧️ ПОЛ:")
        print(f"  ДО:    {gender_before}")
        print(f"  ПОСЛЕ: {gender_after}")
        if gender_before != gender_after:
            print("  ✅ ОБНОВЛЕНО")
        
        # Потоки
        streams_before = before.get('streams') or []
        streams_after = after.get('streams') or []
        
        print(f"\n🌀 ПОТОКИ:")
        print(f"  ДО:    {', '.join(streams_before) if streams_before else 'N/A'}")
        print(f"  ПОСЛЕ: {', '.join(streams_after) if streams_after else 'N/A'}")
        if streams_before != streams_after:
            print("  ✅ ОБНОВЛЕНО")
        
        # Профиль саммари
        profile_before = before.get('profile_summary') or "N/A"
        profile_after = after.get('profile_summary') or "N/A"
        
        print(f"\n📋 ПРОФИЛЬ САММАРИ:")
        print(f"  ДО:    {profile_before}")
        print(f"  ПОСЛЕ: {profile_after}")
        if profile_before != profile_after:
            print("  ✅ ОБНОВЛЕНО")
        
        # Психологическое саммари
        psych_before = before.get('psychological_summary') or "N/A"
        psych_after = after.get('psychological_summary') or "N/A"
        
        print(f"\n🧠 ПСИХОЛОГИЧЕСКОЕ САММАРИ:")
        print(f"  ДО:    {psych_before}")
        print(f"  ПОСЛЕ: {psych_after}")
        if psych_before != psych_after:
            print("  ✅ ОБНОВЛЕНО")
        
        # Статус
        exists_before = before.get('exists', False)
        exists_after = after.get('exists', False)
        
        print(f"\n📊 СТАТУС:")
        if not exists_before and exists_after:
            print("  🆕 НОВЫЙ ПОЛЬЗОВАТЕЛЬ СОЗДАН")
        elif exists_before and exists_after:
            print("  ♻️ СУЩЕСТВУЮЩИЙ ПОЛЬЗОВАТЕЛЬ ОБНОВЛЁН")
        
        print("\n" + "="*80)
    
    async def run_demo(self):
        """Запускает демонстрацию."""
        print("\n" + "="*80)
        print("ДЕМОНСТРАЦИЯ ОБНОВЛЕНИЯ 5 ПОЛЬЗОВАТЕЛЕЙ")
        print("="*80 + "\n")
        
        try:
            # Подключаемся к Telegram
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.error("❌ Not authorized!")
                return
            
            logger.info("✅ Connected to Telegram\n")
            
            # Получаем 5 пользователей из канала
            users = await self.get_5_users_from_channel()
            
            if not users:
                logger.error("❌ No users found!")
                return
            
            logger.info(f"\n✅ Found {len(users)} users\n")
            
            # Для каждого пользователя
            for i, user_data in enumerate(users, 1):
                telegram_id = user_data['telegram_id']
                
                # Получаем состояние ДО
                before = await self.get_user_state_from_db(telegram_id)
                
                # Обновляем через БД напрямую
                logger.info(f"\n{'='*70}")
                logger.info(f"Updating user #{i}: {user_data['first_name']} {user_data['last_name']}")
                logger.info(f"{'='*70}")
                
                await self.update_user_in_db(user_data)
                
                # Получаем состояние ПОСЛЕ
                after = await self.get_user_state_from_db(telegram_id)
                
                # Выводим сравнение
                self.print_user_comparison(before, after, i)
                
                # Пауза между пользователями
                await asyncio.sleep(2)
            
            # Итоговая статистика
            print("\n" + "="*80)
            print("ИТОГОВАЯ СТАТИСТИКА")
            print("="*80)
            print(f"Обработано пользователей: {len(users)}")
            print("="*80 + "\n")
        
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
        
        finally:
            await self.client.disconnect()
            logger.info("\n👋 Disconnected")


async def main():
    """Главная функция."""
    demo = UserUpdateDemo()
    await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main())
