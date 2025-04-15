# TODO: Определить модели данных с использованием ORM (например, SQLAlchemy + asyncpg или Tortoise ORM)
# Либо использовать другую структуру для работы с БД.

# Примерные структуры (можно использовать Pydantic для валидации):

# class User:
#     id: int # Telegram User ID
#     username: str | None
#     first_name: str
#     last_name: str | None
#     registration_date: datetime
#     hero_path_stage: str | None # Текущий этап "Пути Героя"
#     is_admin: bool = False

# class Chat:
#     id: int # Telegram Chat ID
#     title: str | None