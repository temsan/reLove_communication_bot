from sqlalchemy import Column, Integer, String, Boolean, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    """
    Минималистичная модель Telegram-пользователя.
    - id: Telegram user_id
    - username, first_name, last_name: идентификация
    - is_active: активен ли пользователь
    - gender: пол ('male', 'female', 'unknown')
    - context: JSON — персональный контекст (summary, relove_context и др.)
    - markers: JSON — любые пользовательские свойства (гибкие маркеры)
    """
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, doc="Telegram user_id")
    username = Column(String, nullable=True, doc="Telegram username")
    first_name = Column(String, nullable=True, doc="First name")
    last_name = Column(String, nullable=True, doc="Last name")
    is_active = Column(Boolean, default=True, doc="Is user active")
    gender = Column(String, nullable=True, doc="Gender (male, female, unknown)")
    context = Column(JSON, nullable=True, doc="User dialogue context (summary, relove_context и др.)")
    markers = Column(JSON, nullable=True, doc="Словарь свойство-значение для любых пользовательских маркеров и свойств")