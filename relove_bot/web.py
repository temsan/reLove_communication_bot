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
                            photo_b64 = base64.b64encode(u.photo_jpeg).decode('utf-8')
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