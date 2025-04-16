from relove_bot.db.models import User

async def update_user_on_touch(user_id, message, session, extra_context: dict = None, extra_markers: dict = None):
    """
    Обновляет пользователя при любом касании (сообщении, действии и т.д.):
    - Создаёт пользователя, если его нет
    - Обновляет context и markers
    - Сохраняет изменения
    """
    user = await session.get(User, user_id)
    if not user:
        user = User(
            id=user_id,
            username=getattr(message.from_user, 'username', None),
            first_name=getattr(message.from_user, 'first_name', None),
            last_name=getattr(message.from_user, 'last_name', None),
            is_active=True,
            context={},
            markers={}
        )
        session.add(user)
    user.context = user.context or {}
    user.context['last_message'] = getattr(message, 'text', None)
    if extra_context:
        user.context.update(extra_context)
    user.markers = user.markers or {}
    if extra_markers:
        user.markers.update(extra_markers)
    await session.commit()
    return user

async def save_summary(user_id: int, summary: str, session) -> None:
    """
    Сохраняет summary (психологический портрет для общения) в context['summary'] пользователя.
    """
    user = await session.get(User, user_id)
    if not user:
        raise ValueError(f"Пользователь с id={user_id} не найден")
    user.context = user.context or {}
    user.context['summary'] = summary
    await session.commit()

async def set_user_marker(user, key: str, value, session):
    user.markers = user.markers or {}
    user.markers[key] = value
    await session.commit()

async def get_users_by_marker(session, key: str, value) -> list:
    # Вариант для PostgreSQL jsonb
    return (await session.execute(
        User.__table__.select().where(User.markers[key].astext == str(value))
    )).fetchall()
