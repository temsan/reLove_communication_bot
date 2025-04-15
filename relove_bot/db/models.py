from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    """
    Telegram user model.
    Stores user profile, notification preferences, consent, and flexible context for dialogue (summary, relove_context, etc).
    """
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, doc="Telegram user_id")
    username = Column(String, nullable=True, doc="Telegram username")
    first_name = Column(String, nullable=True, doc="First name")
    last_name = Column(String, nullable=True, doc="Last name")
    is_active = Column(Boolean, default=True, doc="Is user active")
    notification_preferences = Column(JSON, nullable=True, doc="Notification preferences")
    last_activity_at = Column(DateTime, nullable=True, doc="Last activity timestamp")
    consent = Column(Boolean, default=False, doc="User consent for data processing")
    context = Column(JSON, nullable=True, doc="User dialogue context (summary, relove_context, hero_path_stage, etc)")

class UserActivityLog(Base):
    """
    User activity log.
    Tracks all user messages, profile summaries, and any activity with optional details and timestamp.
    """
    __tablename__ = 'user_activity_logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, doc="Related user id")
    chat_id = Column(Integer, nullable=True, doc="Telegram chat id")
    activity_type = Column(String, nullable=False, doc="Type of activity: message, profile_summary, etc.")
    timestamp = Column(DateTime, default=datetime.utcnow, doc="Activity timestamp")
    details = Column(JSON, nullable=True, doc="Additional details (dict)")
    summary = Column(Text, nullable=True, doc="Message or profile summary")
    id = Column(Integer, primary_key=True)  # Telegram user_id
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    notification_preferences = Column(JSON, nullable=True)
    last_activity_at = Column(DateTime, nullable=True)
    consent = Column(Boolean, default=False)
    context = Column(JSON, nullable=True)  # Контекст общения пользователя (этап, summary, relove_context и др.)

class UserActivityLog(Base):
    """
    Лог активности пользователя:
    - activity_type: 'message', 'profile_summary' и т.д.
    - summary: summary или агрегированная summary профиля
    """
    __tablename__ = 'user_activity_logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    chat_id = Column(Integer, nullable=True)
    activity_type = Column(String, nullable=False)  # message, profile_summary, etc.
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)

class Chat:
    id: int # Telegram Chat ID
    title: str | None