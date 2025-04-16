import enum
from typing import Optional, Dict, Any
from sqlalchemy import BigInteger, String, Boolean, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, declarative_base

Base = declarative_base()

class GenderEnum(enum.Enum):
    male = "male"
    female = "female"
    unknown = "unknown"

class User(Base):
    """
    Минималистичная модель Telegram-пользователя.
    - id: Telegram user_id
    - username, first_name, last_name: идентификация
    - is_active: активен ли пользователь
    - gender: Enum('male', 'female', 'unknown')
    - context: JSON — персональный контекст (summary, relove_context и др.)
    - markers: JSON — любые пользовательские свойства (гибкие маркеры)
    """
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, doc="Telegram user_id")
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Telegram username")
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="First name")
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Last name")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, doc="Is user active")
    gender: Mapped[Optional[GenderEnum]] = mapped_column(SAEnum(GenderEnum), nullable=True, doc="Gender (male, female, unknown)")
    context: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, doc="User dialogue context (summary, relove_context и др.)")
    markers: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, doc="Словарь свойство-значение для любых пользовательских маркеров и свойств")