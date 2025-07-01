import logging
from aiohttp import web
import aiohttp_jinja2
import jinja2
from relove_bot.db.repository import UserRepository
from relove_bot.db.database import AsyncSessionFactory
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import base64
from aiohttp import web
import aiohttp_jinja2
import jinja2
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from aiohttp.web import HTTPFound
from .config import settings
from datetime import datetime

logger = logging.getLogger(__name__)

async def health_check(request: web.Request):
    logger.debug("Health check requested")
    return web.Response(text="OK")

async def readiness_check(request: web.Request):
    pass

async def admin_panel(request: web.Request):
    from relove_bot.services.admin_stats_service import AdminStatsService
    async with AsyncSessionFactory() as session:
        repo = UserRepository(session)
        stats_service = AdminStatsService(session)
        stats = {
            'total_users': await stats_service.get_total_users(),
            'profiles_with_summary': await stats_service.get_profiles_with_summary(),
            'gender_stats': await stats_service.get_gender_stats(),
        }
        # Получаем приветственное сообщение (можно хранить в файле или базе, здесь для примера — файл)
        try:
            with open('welcome_message.txt', 'r', encoding='utf-8') as f:
                welcome_message = f.read()
        except Exception:
            welcome_message = ''
        return aiohttp_jinja2.render_template('admin.html', request, {'users': [], 'query': '', 'stats': stats, 'welcome_message': welcome_message})

async def admin_search(request: web.Request):
    query = request.rel_url.query.get('query', '').strip()
    users = []
    if query:
        async with AsyncSessionFactory() as session:
            repo = UserRepository(session)
            q = f"%{query.lower()}%"
            sql = """
            SELECT * FROM users WHERE
                CAST(id AS TEXT) ILIKE :q OR
                LOWER(username) ILIKE :q OR
                LOWER(first_name) ILIKE :q OR
                LOWER(last_name) ILIKE :q
            """
            result = await session.execute(sql, {'q': q})
            users = [dict(r) for r in result.fetchall()]
            # Поиск по потокам (markers.streams)
            if not users:
                sql2 = "SELECT * FROM users WHERE markers::text ILIKE :q"
                result2 = await session.execute(sql2, {'q': q})
                users = [dict(r) for r in result2.fetchall()]
    from relove_bot.services.admin_stats_service import AdminStatsService
    async with AsyncSessionFactory() as session:
        stats_service = AdminStatsService(session)
        stats = {
            'total_users': await stats_service.get_total_users(),
            'profiles_with_summary': await stats_service.get_profiles_with_summary(),
            'gender_stats': await stats_service.get_gender_stats(),
        }
        try:
            with open('welcome_message.txt', 'r', encoding='utf-8') as f:
                welcome_message = f.read()
        except Exception:
            welcome_message = ''
    return aiohttp_jinja2.render_template('admin.html', request, {'users': users, 'query': query, 'stats': stats, 'welcome_message': welcome_message})

async def admin_mailing(request: web.Request):
    data = await request.post()
    message = data.get('message', '').strip()
    gender = data.get('gender', '').strip()
    streams = data.getall('streams', [])
    if not message:
        raise web.HTTPFound('/admin')

    async with AsyncSessionFactory() as session:
        repo = UserRepository(session)
        query = "SELECT * FROM users WHERE is_active = true"
        params = {}
        if gender:
            query += " AND gender = :gender"
            params['gender'] = gender
        if streams:
            # streams хранится в markers->'streams', ищем пересечение
            # Пример для PostgreSQL: markers->'streams'::text ILIKE %...%
            # Но markers - JSON, ищем по text
            for idx, stream in enumerate(streams):
                query += f" AND markers::text ILIKE :stream{idx}"
                params[f'stream{idx}'] = f'%{stream}%'
        result = await session.execute(query, params)
        users = [dict(r) for r in result.fetchall()]

        # Здесь отправляем рассылку выбранным пользователям
        # for user in users:
        #     await send_message(user['id'], message)
        # Можно вставить очередь/таски для массовой отправки

    raise web.HTTPFound('/admin')

async def dashboard(request: web.Request):
    from aiohttp import web
    from relove_bot.db.repository import UserRepository
    from relove_bot.db.database import AsyncSessionFactory
    from relove_bot.db.models import User, Registration, Event, Chat, UserActivityLog
    import logging
    logger = logging.getLogger("dashboard")
    
    try:
        async with AsyncSessionFactory() as session:
            repo = UserRepository(session)
            
            # Получаем данные из базы
            users = await session.execute(User.__table__.select())
            users = users.fetchall()
            registrations = await session.execute(Registration.__table__.select())
            registrations = registrations.fetchall()
            events = await session.execute(Event.__table__.select())
            events = events.fetchall()
            chats = await session.execute(Chat.__table__.select())
            chats = chats.fetchall()
            logs = await session.execute(UserActivityLog.__table__.select())
            logs = logs.fetchall()

            # Обработка гендерной статистики
            gender_count = {'male': 0, 'female': 0, 'unknown': 0}
            for u in users:
                try:
                    g = (u.gender.value if hasattr(u.gender, 'value') else u.gender) or 'unknown'
                    gender_count[g] = gender_count.get(g, 0) + 1
                except Exception as e:
                    logger.error(f"Ошибка обработки гендера для пользователя {u.id}: {e}")
                    gender_count['unknown'] += 1

            # Обработка потоков пользователей
            user_streams = {}
            for u in users:
                try:
                    streams = getattr(u, 'streams', []) or []
                    user_streams[u.id] = streams if isinstance(streams, list) else []
                except Exception as e:
                    logger.error(f"Ошибка обработки потоков для пользователя {u.id}: {e}")
                    user_streams[u.id] = []

            # Аналитика постов пользователей
            user_posts_analytics = []
            for u in users:
                try:
                    post_count = sum(1 for l in logs if l.user_id == u.id and l.activity_type in ('message', 'post'))
                    if u.profile_summary or post_count:
                        user_posts_analytics.append({
                            'id': u.id,
                            'gender': (u.gender.value if hasattr(u.gender, 'value') else u.gender) or 'unknown',
                            'summary': u.profile_summary or '',
                            'post_count': post_count
                        })
                except Exception as e:
                    logger.error(f"Ошибка обработки аналитики для пользователя {u.id}: {e}")

            # Данные пользователей
            users_data = []
            for u in users:
                try:
                    photo_b64 = None
                    if hasattr(u, 'photo_jpeg') and u.photo_jpeg:
                        try:
                            if isinstance(u.photo_jpeg, bytes):
                                photo_b64 = base64.b64encode(u.photo_jpeg).decode('utf-8')
                            elif isinstance(u.photo_jpeg, str):
                                # Если это уже base64 строка, используем её как есть
                                photo_b64 = u.photo_jpeg
                        except Exception as e:
                            logger.error(f"Ошибка кодирования фото для пользователя {u.id}: {e}")
                    
                    post_count = sum(1 for l in logs if l.user_id == u.id and l.activity_type in ('message', 'post'))
                    streams = getattr(u, 'streams', []) or []
                    streams_count = len(streams) if isinstance(streams, list) else 0
                    
                    users_data.append({
                        'id': u.id,
                        'photo_jpeg': photo_b64,
                        'first_name': u.first_name or '',
                        'last_name': u.last_name or '',
                        'username': u.username or '',
                        'gender': (u.gender.value if hasattr(u.gender, 'value') else u.gender) or '',
                        'profile_summary': u.profile_summary or '',
                        'streams_count': streams_count,
                        'post_count': post_count,
                        'is_active': getattr(u, 'is_active', False),
                        'streams': streams if isinstance(streams, list) else []
                    })
                except Exception as e:
                    logger.error(f"Ошибка обработки данных пользователя {u.id}: {e}")

            # Статистика потоков
            from collections import Counter
            all_streams = []
            for streams in user_streams.values():
                if isinstance(streams, list):
                    all_streams.extend(streams)
            stream_counter = Counter(all_streams)
            stream_labels = list(stream_counter.keys())
            stream_counts = list(stream_counter.values())

            # Подготовка данных для графиков
            male_count = gender_count.get('male', 0) or 0
            female_count = gender_count.get('female', 0) or 0
            unknown_count = gender_count.get('unknown', 0) or 0
            stream_labels = stream_labels if stream_labels else []
            stream_counts = stream_counts if stream_counts else []
            
            # Подсчет общей статистики
            total_users = len(users)
            total_events = len(events)
            total_streams = sum(len(streams) for streams in user_streams.values() if isinstance(streams, list))
            total_posts = sum(1 for l in logs if l.activity_type in ('message', 'post'))

            # Статистика по потокам
            stream_stats = {
                'Мужской': {'participants': 0, 'active': 0, 'completed': 0},
                'Женский': {'participants': 0, 'active': 0, 'completed': 0},
                'Смешанный': {'participants': 0, 'active': 0, 'completed': 0},
                'Путь Героя': {'participants': 0, 'active': 0, 'completed': 0}
            }

            # Подсчет статистики по потокам
            for user in users:
                streams = getattr(user, 'streams', []) or []
                if isinstance(streams, list):
                    for stream in streams:
                        if stream in stream_stats:
                            stream_stats[stream]['participants'] += 1
                            if getattr(user, 'is_active', False):
                                stream_stats[stream]['active'] += 1
                            if getattr(user, 'completed', False):
                                stream_stats[stream]['completed'] += 1

            # Подготовка данных для графиков активности
            activity_data = []
            activity_labels = []
            for log in sorted(logs, key=lambda x: x.timestamp):
                if log.activity_type in ('message', 'post'):
                    activity_data.append(1)
                    activity_labels.append(log.timestamp.strftime('%Y-%m-%d'))

            # Подготовка данных для психотипов
            psychotype_labels = ['Интроверт', 'Экстраверт', 'Амбиверт']
            psychotype_counts = [0, 0, 0]
            for user in users:
                psychotype = getattr(user, 'psychotype', '')
                if psychotype in psychotype_labels:
                    idx = psychotype_labels.index(psychotype)
                    psychotype_counts[idx] += 1

            # Подготовка данных для эмоционального анализа
            emotion_labels = ['Радость', 'Грусть', 'Гнев', 'Страх', 'Удивление']
            emotion_data = [0, 0, 0, 0, 0]
            for user in users:
                emotions = getattr(user, 'emotions', {}) or {}
                for i, emotion in enumerate(emotion_labels):
                    emotion_data[i] += emotions.get(emotion, 0)

            return aiohttp_jinja2.render_template('dashboard.html', request, {
                'users': users_data,
                'events': events,
                'registrations': registrations,
                'logs': logs,
                'gender_count': gender_count,
                'user_streams': user_streams,
                'stream_labels': stream_labels,
                'stream_counts': stream_counts,
                'user_posts_analytics': user_posts_analytics,
                'male_count': male_count,
                'female_count': female_count,
                'unknown_count': unknown_count,
                'total_users': total_users,
                'total_events': total_events,
                'total_streams': total_streams,
                'total_posts': total_posts,
                'stream_stats': stream_stats,
                'activity_data': activity_data,
                'activity_labels': activity_labels,
                'psychotype_labels': psychotype_labels,
                'psychotype_counts': psychotype_counts,
                'emotion_labels': emotion_labels,
                'emotion_data': emotion_data,
                'active_users_today': sum(1 for u in users if getattr(u, 'is_active', False)),
                'new_users_week': sum(1 for u in users if getattr(u, 'created_at', None) and (datetime.now() - u.created_at).days <= 7),
                'analyzed_users': sum(1 for u in users if getattr(u, 'profile_summary', None))
            })
    except Exception as e:
        logger.error(f"Критическая ошибка в дашборде: {e}", exc_info=True)
        return web.Response(text=f"Ошибка загрузки дашборда: {str(e)}", status=500)

# --- Новый endpoint для API автообновления дашборда ---
async def dashboard_data_api(request: web.Request):
    import base64
    from relove_bot.db.repository import UserRepository
    from relove_bot.db.database import AsyncSessionFactory
    from relove_bot.db.models import User, UserActivityLog
    from aiohttp import web
    async with AsyncSessionFactory() as session:
        users = await session.execute(User.__table__.select())
        users = users.fetchall()
        logs = await session.execute(UserActivityLog.__table__.select())
        logs = logs.fetchall()
        gender_count = {'male': 0, 'female': 0, 'unknown': 0}
        for u in users:
            g = (u.gender.value if hasattr(u.gender, 'value') else u.gender) or 'unknown'
            gender_count[g] = gender_count.get(g, 0) + 1
        user_streams = {u.id: getattr(u, 'streams', []) for u in users}
        users_data = []
        for u in users:
            photo_b64 = base64.b64encode(u.photo_jpeg).decode('utf-8') if hasattr(u, 'photo_jpeg') and isinstance(u.photo_jpeg, (bytes, bytearray)) and u.photo_jpeg else None
            post_count = sum(1 for l in logs if l.user_id == u.id and l.activity_type in ('message', 'post'))
            users_data.append({
                'id': u.id,
                'photo_jpeg': photo_b64,
                'first_name': u.first_name or '',
                'last_name': u.last_name or '',
                'username': u.username or '',
                'gender': u.gender.value if u.gender else '',
                'profile_summary': u.profile_summary or '',
                'streams_count': len(getattr(u, 'streams', []) or []),
                'post_count': post_count,
            })
        from collections import Counter
        all_streams = []
        for streams in user_streams.values():
            if streams:
                all_streams.extend(streams)
        stream_counter = Counter(all_streams)
        stream_labels = list(stream_counter.keys())
        stream_counts = list(stream_counter.values())
        return web.json_response({
            'users': users_data,
            'male_count': gender_count['male'],
            'female_count': gender_count['female'],
            'unknown_count': gender_count['unknown'],
            'stream_labels': stream_labels,
            'stream_counts': stream_counts,
        })

async def setup_webhook(bot: Bot, dispatcher: Dispatcher):
    if not settings.webhook_host:
        logger.warning("WEBHOOK_HOST not set, skipping webhook setup.")
        return None

    webhook_url = f"{settings.webhook_host}{settings.webhook_path}"
    webhook_secret = settings.webhook_secret.get_secret_value() if settings.webhook_secret else None

    try:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=webhook_secret,
            # drop_pending_updates=True # Раскомментировать, если нужно сбрасывать старые апдейты при старте
        )
        logger.info(f"Webhook set up successfully at {webhook_url}")
        return webhook_url
    except Exception as e:
        logger.error(f"Failed to set webhook at {webhook_url}: {e}", exc_info=True)
        return None

async def on_startup(app: web.Application):
    """Actions to perform on web server startup."""
    bot: Bot = app['bot']
    dp: Dispatcher = app['dp']
    logger.info("Web server starting up...")
    await setup_webhook(bot, dp)
    # Здесь можно добавить инициализацию подключения к БД
    # app['db_pool'] = await create_db_pool()
    logger.info("Web server startup complete.")

async def on_shutdown(app: web.Application):
    """Actions to perform on web server shutdown."""
    bot: Bot = app['bot']
    logger.info("Web server shutting down...")
    # Удаляем вебхук при остановке
    # await bot.delete_webhook()
    # logger.info("Webhook deleted.")
    # Закрываем соединение с БД
    # if 'db_pool' in app:
    #    await app['db_pool'].close()
    #    logger.info("Database pool closed.")
    await bot.session.close()
    logger.info("Bot session closed.")
    logger.info("Web server shutdown complete.")

def b64encode(value):
    return base64.b64encode(value).decode('utf-8')

async def aiohttp_startup(app):
    from relove_bot.db.database import setup_database
    await setup_database()

@web.middleware
async def welcome_message_middleware(request, handler):
    if request.path == '/admin/welcome' and request.method == 'POST':
        data = await request.post()
        welcome_message = data.get('welcome_message', '').strip()
        with open('welcome_message.txt', 'w', encoding='utf-8') as f:
            f.write(welcome_message)
        raise web.HTTPFound('/admin')
    return await handler(request)

@web.middleware
async def reminder_middleware(request, handler):
    if request.path == '/admin/reminder' and request.method == 'POST':
        from relove_bot.services.reminder_service import ReminderService
        import time
        data = await request.post()
        user_id = int(data.get('user_id'))
        text = data.get('reminder_message', '').strip()
        reminder_time = int(data.get('reminder_time'))
        reminder_service = ReminderService()
        await reminder_service.schedule_reminder(user_id, text, reminder_time)
        raise web.HTTPFound('/admin')
    return await handler(request)

@web.middleware
async def analyze_gender_middleware(request, handler):
    if request.path == '/admin/analyze_gender' and request.method == 'POST':
        from relove_bot.services.gender_analysis_service import GenderAnalysisService
        async with AsyncSessionFactory() as session:
            repo = UserRepository(session)
            users = await session.execute("SELECT id FROM users WHERE gender IS NULL")
            users = [row[0] for row in users.fetchall()]
            gender_service = GenderAnalysisService(session)
            for uid in users:
                await gender_service.analyze_and_save_gender(uid)
        raise web.HTTPFound('/admin')
    return await handler(request)

async def analyze_user(request: web.Request):
    user_id = request.match_info.get('user_id')
    if not user_id:
        return web.json_response({'error': 'User ID is required'}, status=400)
    
    try:
        async with AsyncSessionFactory() as session:
            repo = UserRepository(session)
            user = await repo.get_user_by_id(int(user_id))
            if not user:
                return web.json_response({'error': 'User not found'}, status=404)
            
            # Анализ профиля пользователя
            analysis = {
                'psychotype': user.psychotype or 'Не определен',
                'emotional_state': user.emotional_state or 'Не определен',
                'activity_level': user.activity_level or 'Не определен',
                'interests': user.interests or [],
                'recommendations': user.recommendations or []
            }
            
            return web.json_response(analysis)
    except Exception as e:
        logger.error(f"Error analyzing user {user_id}: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def user_details(request: web.Request):
    user_id = request.match_info.get('user_id')
    if not user_id:
        return web.json_response({'error': 'User ID is required'}, status=400)
    
    try:
        async with AsyncSessionFactory() as session:
            repo = UserRepository(session)
            user = await repo.get_user_by_id(int(user_id))
            if not user:
                return web.json_response({'error': 'User not found'}, status=404)
            
            # Получаем детальную информацию о пользователе
            details = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'gender': user.gender,
                'registration_date': user.registration_date.isoformat() if user.registration_date else None,
                'last_activity': user.last_activity.isoformat() if user.last_activity else None,
                'streams': user.streams or [],
                'psychotype': user.psychotype,
                'emotional_state': user.emotional_state,
                'activity_level': user.activity_level,
                'profile_summary': user.profile_summary,
                'is_active': user.is_active,
                'completed': user.completed
            }
            
            return web.json_response(details)
    except Exception as e:
        logger.error(f"Error getting user details {user_id}: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def update_user_status(request: web.Request):
    user_id = request.match_info.get('user_id')
    if not user_id:
        return web.json_response({'error': 'User ID is required'}, status=400)
    
    try:
        data = await request.json()
        status = data.get('status')
        if not status:
            return web.json_response({'error': 'Status is required'}, status=400)
        
        async with AsyncSessionFactory() as session:
            repo = UserRepository(session)
            user = await repo.get_user_by_id(int(user_id))
            if not user:
                return web.json_response({'error': 'User not found'}, status=404)
            
            # Обновляем статус пользователя
            user.is_active = status == 'active'
            await session.commit()
            
            return web.json_response({'success': True})
    except Exception as e:
        logger.error(f"Error updating user status {user_id}: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def manage_streams(request: web.Request):
    try:
        data = await request.json()
        action = data.get('action')
        stream_name = data.get('stream_name')
        user_id = data.get('user_id')
        
        if not all([action, stream_name, user_id]):
            return web.json_response({'error': 'All fields are required'}, status=400)
        
        async with AsyncSessionFactory() as session:
            repo = UserRepository(session)
            user = await repo.get_user_by_id(int(user_id))
            if not user:
                return web.json_response({'error': 'User not found'}, status=404)
            
            streams = user.streams or []
            if action == 'add' and stream_name not in streams:
                streams.append(stream_name)
            elif action == 'remove' and stream_name in streams:
                streams.remove(stream_name)
            
            user.streams = streams
            await session.commit()
            
            return web.json_response({'success': True, 'streams': streams})
    except Exception as e:
        logger.error(f"Error managing streams: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def automation_settings(request: web.Request):
    try:
        data = await request.json()
        action = data.get('action')
        settings = data.get('settings')
        
        if not action:
            return web.json_response({'error': 'Action is required'}, status=400)
        
        async with AsyncSessionFactory() as session:
            if action == 'get':
                # Получаем текущие настройки автоматизации
                settings = await session.execute("SELECT * FROM automation_settings")
                settings = settings.fetchone()
                return web.json_response(settings or {})
            
            elif action == 'update':
                if not settings:
                    return web.json_response({'error': 'Settings are required'}, status=400)
                
                # Обновляем настройки автоматизации
                await session.execute(
                    "UPDATE automation_settings SET settings = :settings WHERE id = 1",
                    {'settings': settings}
                )
                await session.commit()
                return web.json_response({'success': True})
            
            else:
                return web.json_response({'error': 'Invalid action'}, status=400)
    except Exception as e:
        logger.error(f"Error managing automation settings: {e}")
        return web.json_response({'error': str(e)}, status=500)

def create_dashboard_app() -> web.Application:
    """Создаёт и конфигурирует aiohttp web приложение только для дашборда."""
    import os
    templates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    app = web.Application()
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(templates_path),
        filters={
            'b64encode': b64encode
        }
    )

    # --- Роуты для дашборда ---
    app.router.add_get('/dashboard', dashboard)
    app.router.add_get('/', lambda request: web.HTTPFound('/dashboard'))  # Перенаправление с корня на дашборд

    # Добавить статические файлы (css/js/images)
    static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', static_path, name='static')

    # --- Роут для API данных дашборда ---
    app.router.add_get('/api/dashboard_data', dashboard_data_api)


    # Добавляем обработчики startup и shutdown
    async def startup_wrapper(app):
        from relove_bot.db.database import setup_database
        await setup_database()
    
    app.on_startup.clear()
    app.on_startup.append(startup_wrapper)
    
    logger.info("Dashboard application created")
    return app

def create_app(bot: Bot, dp: Dispatcher) -> web.Application:
    """Создаёт и конфигурирует aiohttp web приложение с кастомным фильтром b64encode для Jinja2."""
    import os
    templates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    app = web.Application()
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(templates_path),
        filters={
            'b64encode': b64encode
        }
    )

    # Сохраняем экземпляры Bot и Dispatcher для доступа в обработчиках
    app['bot'] = bot
    app['dp'] = dp

    # --- Роуты для панели администратора и дашборда ---
    app.router.add_get('/admin', admin_panel)
    app.router.add_get('/admin/search', admin_search)
    app.router.add_post('/admin/mailing', admin_mailing)
    app.router.add_get('/dashboard', dashboard)

    # Добавить статические файлы (css/js/images)
    static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', static_path, name='static')

    # --- Новый роут для API данных дашборда ---
    app.router.add_get('/api/dashboard_data', dashboard_data_api)

    # Добавляем новые маршруты
    app.router.add_get('/api/user/{user_id}/analyze', analyze_user)
    app.router.add_get('/api/user/{user_id}/details', user_details)
    app.router.add_post('/api/user/{user_id}/status', update_user_status)
    app.router.add_post('/api/streams/manage', manage_streams)
    app.router.add_post('/api/automation/settings', automation_settings)

    # Настраиваем приложение aiogram (необходимо для SimpleRequestHandler)
    setup_application(app, dp, bot=bot)

    # Добавляем обработчики startup и shutdown
    async def startup_wrapper(app):
        from relove_bot.db.database import setup_database
        await setup_database()
        await on_startup(app)
    app.on_startup.clear()
    app.on_startup.append(startup_wrapper)
    app.on_shutdown.append(on_shutdown)

    logger.info(f"aiohttp application created. Webhook path: {settings.webhook_path}")
    return app
    return app 