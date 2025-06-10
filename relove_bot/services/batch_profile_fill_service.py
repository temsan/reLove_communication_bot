"""
Сервис для пакетного заполнения профилей пользователей.
"""
import asyncio
import logging
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

from relove_bot.config import settings
from relove_bot.utils.fill_profiles import fill_all_profiles
from relove_bot.services.telegram_service import get_client, get_channel_users
from telethon.tl.functions.channels import GetFullChannelRequest
from relove_bot.db.session import get_session

logger = logging.getLogger(__name__)

def create_progress_callback(pbar, total_users, batch_number=None, position=0):
    """
    Создает функцию обратного вызова для обновления прогресса
    
    Args:
        pbar: Прогресс-бар tqdm
        total_users: Общее количество пользователей
        batch_number: Номер текущей пачки (опционально)
        position: Позиция прогресс-бара (0 - основной, 1 - вложенный)
    """
    def update_progress(processed, total, message):
        if pbar:
            desc = f"Пачка {batch_number}: {message}" if batch_number else message
            if len(desc) > 80:  # Ограничиваем длину описания
                desc = desc[:77] + "..."
            pbar.set_description(desc)
            pbar.update(1)
            pbar.refresh()
            # Перемещаем курсор вниз после обновления, чтобы логи не перекрывали прогресс-бар
            print("\n" * (2 - position), end="", flush=True)
    return update_progress

async def process_all_channel_profiles_batch(channel_username: str, batch_size: int = 200):
    """
    Получает пользователей из канала порциями по batch_size и передаёт их на запись в fill_all_profiles.
    
    Args:
        channel_username: Имя или ID канала
        batch_size: Количество пользователей для обработки за один раз (макс. 200)
    """
    client = None
    processed_count = 0
    batch_number = 1
    
    try:
        # Инициализация клиента
        client = await get_client()
        if not client:
            logger.critical("Не удалось получить Telegram клиента.")
            return
            
        # Убеждаемся, что клиент подключен
        if not client.is_connected():
            await client.connect()
            
        if not await client.is_user_authorized():
            logger.critical("Клиент не авторизован.")
            return
            
        logger.info(f"Начинаем обработку пользователей канала {channel_username}...")
        
        # Получаем общее количество пользователей для отображения прогресса
        total_users = None
        try:
            # Получаем количество участников канала
            full_channel = await client(GetFullChannelRequest(await client.get_entity(channel_username)))
            total_users = getattr(full_channel.full_chat, 'participants_count', 0)
            logger.info(f"Всего пользователей в канале: {total_users}")
        except Exception as e:
            logger.error(f"Не удалось получить количество пользователей: {e}")
        
        # Создаем список для сбора пользователей
        user_list = []
        
        # Если не удалось получить общее количество, будем обновлять прогресс по мере сбора
        if total_users is None:
            logger.info("Не удалось получить общее количество пользователей. Будет отображаться только прогресс сбора.")
            pbar = tqdm(
                desc="Сбор пользователей",
                unit=" польз.",
                position=0,
                leave=True,
                dynamic_ncols=True,
                bar_format='{desc}: {n_fmt} {unit} [{elapsed}, {rate_fmt}{postfix}]'
            )
        else:
            logger.info(f"Всего пользователей для обработки: {total_users}")
            pbar = tqdm(
                desc="Сбор пользователей",
                total=total_users,
                unit=" польз.",
                position=0,
                leave=True,
                dynamic_ncols=True,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]'
            )
        
        # Используем контекстный менеджер для прогресс-бара
        with pbar as collection_pbar:
            
            # Собираем пользователей пачками
            current_batch = []
            
            async for user_id in get_channel_users(channel_username, batch_size=batch_size):
                if not user_id:
                    continue
                    
                current_batch.append(user_id)
                processed_count += 1
                
                # Обновляем прогресс
                try:
                    collection_pbar.update(1)
                    collection_pbar.set_postfix_str(f"Обработано: {processed_count}")
                    collection_pbar.refresh()
                except Exception as e:
                    logger.debug(f"Ошибка при обновлении прогресс-бара: {e}")
                
                # Когда набрали нужное количество пользователей, обрабатываем пачку
                if len(current_batch) >= batch_size:
                    batch_desc = f"Пачка {batch_number}"
                    logger.info(f"Обработка {batch_desc} ({len(current_batch)} пользователей)...")
                    
                    # Создаем прогресс-бар для обработки текущей пачки
                    # Вложенный прогресс-бар с position=1 (выше основного)
                    with tqdm(
                        total=len(current_batch),
                        desc=batch_desc,
                        unit="польз.",
                        position=1,
                        leave=False,
                        dynamic_ncols=True,
                        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]'
                    ) as pbar_batch:
                        progress_callback = create_progress_callback(pbar_batch, len(current_batch), batch_number)
                        
                        try:
                            # Создаем новую сессию для каждой пачки
                            async with get_session() as session:
                                await fill_all_profiles(
                                    users=current_batch,
                                    client=client,
                                    session=session,
                                    progress_callback=progress_callback
                                )
                            logger.info(f"{batch_desc} успешно обработана. Всего: {processed_count}")
                        except Exception as e:
                            logger.error(f"Ошибка при обработке {batch_desc}: {e}", exc_info=True)
                    
                    # Очищаем текущую пачку и увеличиваем счетчик
                    current_batch = []
                    batch_number += 1
            
            # Обработка оставшихся пользователей в последней пачке
            if current_batch:
                batch_desc = f"Последняя пачка {batch_number}"
                logger.info(f"Начало обработки последней пачки из {len(current_batch)} пользователей")
                with tqdm(
                    total=len(current_batch),
                    desc=batch_desc,
                    unit="польз.",
                    position=1,
                    leave=False,
                    dynamic_ncols=True,
                    bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]'
                ) as pbar_batch:
                    progress_callback = create_progress_callback(pbar_batch, len(current_batch), batch_number)
                    
                    try:
                        # Создаем новую сессию для последней пачки
                        async with get_session() as session:
                            await fill_all_profiles(
                                users=current_batch,
                                client=client,
                                session=session,
                                progress_callback=progress_callback
                            )
                        logger.info(f"{batch_desc} успешно обработана. Всего: {processed_count}")
                    except Exception as e:
                        logger.error(f"Ошибка при обработке {batch_desc}: {e}", exc_info=True)
        
        logger.info(f"Обработка всех пользователей завершена. Всего обработано: {processed_count}")
        
    except Exception as e:
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
        raise
    finally:
        try:
            if client and client.is_connected():
                await client.disconnect()
        except Exception as e:
            logger.error(f"Ошибка при отключении клиента: {e}")