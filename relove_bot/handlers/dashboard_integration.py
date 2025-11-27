"""
Интеграция функционала анализа профиля и автоматических сообщений в дашборд.
"""
from aiohttp import web
import logging

from relove_bot.services.profile_analyzer import get_profile_analyzer
from relove_bot.services.natasha_service import get_natasha_service
from relove_bot.services.journey_service import get_journey_service
from relove_bot.db.database import AsyncSessionFactory
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def dashboard_analyze_user(request: web.Request):
    """Анализирует профиль пользователя через дашборд."""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        
        if not user_id:
            return web.json_response({'error': 'User ID is required'}, status=400)
        
        profile_analyzer = get_profile_analyzer()
        
        # Получи информацию о пользователе из БД
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                text("SELECT * FROM users WHERE id = :user_id"),
                {'user_id': user_id}
            )
            user = result.fetchone()
            
            if not user:
                return web.json_response({'error': 'User not found'}, status=404)
            
            # Получи посты пользователя
            posts_result = await session.execute(
                text("SELECT content FROM user_activity_logs WHERE user_id = :user_id AND activity_type = 'post' LIMIT 20"),
                {'user_id': user_id}
            )
            posts = [row[0] for row in posts_result.fetchall()]
            
            # Анализируй профиль
            profile_data = profile_analyzer.analyze_profile(
                user_id=str(user_id),
                bio=user.first_name or "",
                posts=posts,
                channel_posts=[],
            )
            
            return web.json_response({
                'success': True,
                'analysis': {
                    'emotional_state': profile_data['state']['emotional_state'],
                    'energy_level': profile_data['state']['energy_level'],
                    'focus_areas': profile_data['state']['focus_areas'],
                    'challenges': profile_data['state']['challenges'],
                    'growth_indicators': profile_data['state']['growth_indicators'],
                    'topic': profile_data['topic'],
                }
            })
    
    except Exception as e:
        logger.error(f"Error analyzing user {user_id}: {e}", exc_info=True)
        return web.json_response({'error': str(e)}, status=500)


async def dashboard_generate_message(request: web.Request):
    """Генерирует сообщение на основе анализа профиля."""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        
        if not user_id:
            return web.json_response({'error': 'User ID is required'}, status=400)
        
        profile_analyzer = get_profile_analyzer()
        natasha_service = get_natasha_service()
        
        # Получи информацию о пользователе
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                text("SELECT * FROM users WHERE id = :user_id"),
                {'user_id': user_id}
            )
            user = result.fetchone()
            
            if not user:
                return web.json_response({'error': 'User not found'}, status=404)
            
            # Получи посты
            posts_result = await session.execute(
                text("SELECT content FROM user_activity_logs WHERE user_id = :user_id AND activity_type = 'post' LIMIT 20"),
                {'user_id': user_id}
            )
            posts = [row[0] for row in posts_result.fetchall()]
            
            # Анализируй профиль
            profile_data = profile_analyzer.analyze_profile(
                user_id=str(user_id),
                bio=user.first_name or "",
                posts=posts,
            )
            
            # Сгенерируй сообщение
            generated_message = profile_analyzer.generate_message(str(user_id), profile_data)
            
            if not generated_message:
                return web.json_response({'error': 'Could not generate message'}, status=400)
            
            # Получи ответ Наташи
            result = await natasha_service.get_response(
                user_id=str(user_id),
                message=generated_message
            )
            
            return web.json_response({
                'success': True,
                'generated_message': generated_message,
                'natasha_response': result.get('response') if result.get('success') else None,
                'topic': result.get('topic') if result.get('success') else None,
            })
    
    except Exception as e:
        logger.error(f"Error generating message for user {user_id}: {e}", exc_info=True)
        return web.json_response({'error': str(e)}, status=500)


async def dashboard_user_journey(request: web.Request):
    """Получает путь пользователя за период."""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        period = data.get('period', 'week')  # yesterday, week, month, или число дней
        
        if not user_id:
            return web.json_response({'error': 'User ID is required'}, status=400)
        
        journey_service = get_journey_service()
        
        # Получи путь за период
        journey_entries = journey_service.get_journey_for_period(str(user_id), period)
        
        if not journey_entries:
            return web.json_response({
                'success': True,
                'journey': [],
                'summary': f'No entries for {period}'
            })
        
        # Консолидируй путь
        consolidation = journey_service.consolidate_journey(str(user_id), period)
        
        return web.json_response({
            'success': True,
            'journey': journey_entries,
            'consolidation': {
                'period': consolidation['period'],
                'total_entries': consolidation['total_entries'],
                'topics': consolidation['topics'],
                'date_range': consolidation['date_range'],
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting user journey for {user_id}: {e}", exc_info=True)
        return web.json_response({'error': str(e)}, status=500)


async def dashboard_user_separations(request: web.Request):
    """Получает разделения пути пользователя."""
    try:
        user_id = request.match_info.get('user_id')
        
        if not user_id:
            return web.json_response({'error': 'User ID is required'}, status=400)
        
        journey_service = get_journey_service()
        
        # Получи разделения
        separations = journey_service.get_all_separations(str(user_id))
        
        return web.json_response({
            'success': True,
            'separations': separations
        })
    
    except Exception as e:
        logger.error(f"Error getting user separations for {user_id}: {e}", exc_info=True)
        return web.json_response({'error': str(e)}, status=500)


# Регистрация маршрутов
def setup_dashboard_routes(app: web.Application):
    """Регистрирует маршруты для интеграции с дашбордом."""
    app.router.add_post('/api/dashboard/analyze-user', dashboard_analyze_user)
    app.router.add_post('/api/dashboard/generate-message', dashboard_generate_message)
    app.router.add_post('/api/dashboard/user-journey', dashboard_user_journey)
    app.router.add_get('/api/dashboard/user-separations/{user_id}', dashboard_user_separations)
