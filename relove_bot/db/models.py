import datetime
from typing import Optional, List, Dict, Any

import enum
from sqlalchemy import BigInteger, String, DateTime, Text, ForeignKey, Integer, Boolean, JSON, LargeBinary
from sqlalchemy.types import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, declarative_base
from sqlalchemy.sql import func

# Убираем импорт database.Base и используем declarative_base здесь, как в вашем последнем изменении
# from .database import Base
Base = declarative_base()

class GenderEnum(enum.Enum):
    male = "male"
    female = "female"
    unknown = "unknown"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True, autoincrement=False, doc="Telegram User ID")
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    registration_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    gender: Mapped[Optional[GenderEnum]] = mapped_column(SQLEnum(GenderEnum, name='genderenum'), nullable=True, index=True, doc="Пол пользователя (male/female/unknown)")
    history_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Выжимка истории общения с ботом")
    profile_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Выжимка профиля (посты, фото и т.д.)") 
    photo_jpeg: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary, nullable=True, doc="Фото профиля (JPEG, сжато)"
    )
    markers: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, doc="Словарь свойство-значение для любых пользовательских маркеров и свойств"
    )
    streams: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, doc="Список пройденных потоков reLove")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    registrations: Mapped[List["Registration"]] = relationship(back_populates="user")
    activity_logs: Mapped[List["UserActivityLog"]] = relationship(back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, name={self.first_name}, gender={self.gender})>"

class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True, autoincrement=False, doc="Telegram Chat ID")
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, doc="private, group, supergroup, channel")
    registration_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    activity_logs: Mapped[List["UserActivityLog"]] = relationship(back_populates="chat")

    def __repr__(self):
        return f"<Chat(id={self.id}, title={self.title}, type={self.type})>"

class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, index=True, doc="Поток, Ритуал, ПГ и т.д.")
    max_participants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    registration_deadline: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    registrations: Mapped[List["Registration"]] = relationship(back_populates="event")

    def __repr__(self):
        return f"<Event(id={self.id}, title={self.title}, type={self.type}, start={self.start_time})>"

class Registration(Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"), index=True)
    registration_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String, default="registered", index=True, doc="registered, attended, cancelled")

    user: Mapped["User"] = relationship(back_populates="registrations")
    event: Mapped["Event"] = relationship(back_populates="registrations")

    def __repr__(self):
        return f"<Registration(id={self.id}, user_id={self.user_id}, event_id={self.event_id}, status={self.status})>"

class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("chats.id"), nullable=True, index=True)
    activity_type: Mapped[str] = mapped_column(String, index=True, doc="command, message, callback_query, event_registration, etc.")
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, doc="Доп. данные: текст команды, callback_data, id сообщения и т.п.")

    user: Mapped["User"] = relationship(back_populates="activity_logs")
    chat: Mapped[Optional["Chat"]] = relationship(back_populates="activity_logs")

    def __repr__(self):
        return f"<UserActivityLog(id={self.id}, user_id={self.user_id}, type={self.activity_type}, time={self.timestamp})>"