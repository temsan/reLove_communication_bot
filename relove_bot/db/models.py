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

class PsychotypeEnum(enum.Enum):
    ANALYTICAL = "Аналитический"
    EMOTIONAL = "Эмоциональный"
    INTUITIVE = "Интуитивный"
    PRACTICAL = "Практический"

class JourneyStageEnum(enum.Enum):
    ORDINARY_WORLD = "Обычный мир"
    CALL_TO_ADVENTURE = "Зов к приключению"
    REFUSAL = "Отказ от призыва"
    MEETING_MENTOR = "Встреча с наставником"
    CROSSING_THRESHOLD = "Пересечение порога"
    TESTS_ALLIES_ENEMIES = "Испытания, союзники, враги"
    APPROACH = "Приближение к сокровенной пещере"
    ORDEAL = "Испытание"
    REWARD = "Награда"
    ROAD_BACK = "Дорога назад"
    RESURRECTION = "Воскресение"
    RETURN_WITH_ELIXIR = "Возвращение с эликсиром"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True, autoincrement=False, doc="Telegram User ID")
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    registration_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    gender: Mapped[Optional[GenderEnum]] = mapped_column(SQLEnum(GenderEnum, name='genderenum'), nullable=True, default=None, index=True, doc="Пол пользователя (male/female)")
    history_summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, 
        doc="История диалогов с ботом. Использование: контекст для персонализации ответов"
    )
    profile: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, 
        doc="Психопрофиль из постов/био/каналов. Цель: понимание личности для подбора подхода"
    )
    hero_stage: Mapped[Optional[JourneyStageEnum]] = mapped_column(
        SQLEnum(JourneyStageEnum), nullable=True, index=True, 
        doc="Этап пути героя. Цель: определение текущей точки трансформации для выбора стратегии"
    )
    metaphysics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, 
        doc="Метафизика (планета, карма, свет/тьма). Цель: глубинный архетипический контекст"
    )
    photo_jpeg: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary, nullable=True, doc="Фото профиля (JPEG, сжато)"
    )
    markers: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, doc="Кастомные маркеры и свойства"
    )
    streams: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, doc="Пройденные потоки reLove"
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Поля для отслеживания конверсии
    has_started_journey: Mapped[bool] = mapped_column(Boolean, default=False)
    has_completed_journey: Mapped[bool] = mapped_column(Boolean, default=False)
    has_visited_platform: Mapped[bool] = mapped_column(Boolean, default=False)
    has_purchased_flow: Mapped[bool] = mapped_column(Boolean, default=False)

    registrations: Mapped[List["Registration"]] = relationship(back_populates="user")
    activity_logs: Mapped[List["UserActivityLog"]] = relationship(back_populates="user")
    diagnostic_results: Mapped[List["DiagnosticResult"]] = relationship("DiagnosticResult", back_populates="user")
    journey_progress: Mapped[List["JourneyProgress"]] = relationship("JourneyProgress", back_populates="user")
    sessions: Mapped[List["UserSession"]] = relationship("UserSession", back_populates="user")

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


class UserActivityLogArchive(Base):
    """Архив старых логов активности (старше 90 дней)"""
    __tablename__ = "user_activity_logs_archive"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    activity_type: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    archived_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    def __repr__(self):
        return f"<UserActivityLogArchive(id={self.id}, user_id={self.user_id}, type={self.activity_type})>"


class YouTubeChatUser(Base):
    __tablename__ = "youtube_chat_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    youtube_display_name: Mapped[str] = mapped_column(String, nullable=False, comment="Отображаемое имя в YouTube чате")
    youtube_channel_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, comment="ID канала пользователя в YouTube")
    message_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False, comment="Количество сообщений в чате")
    first_seen: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Дата первого сообщения")
    last_seen: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Дата последнего сообщения")
    telegram_username: Mapped[Optional[str]] = mapped_column(String, nullable=True, comment="Найденный username в Telegram")
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="ID пользователя в Telegram, если найден")
    is_community_member: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False, comment="Является ли участником сообщества")
    user_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, comment="Дополнительные данные пользователя")

    def __repr__(self):
        return f"<YouTubeChatUser(id={self.id}, name={self.youtube_display_name}, tg={self.telegram_username or 'N/A'})>"

class DiagnosticResult(Base):
    __tablename__ = "diagnostic_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    psychotype: Mapped[PsychotypeEnum] = mapped_column(SQLEnum(PsychotypeEnum), index=True)
    journey_stage: Mapped[JourneyStageEnum] = mapped_column(SQLEnum(JourneyStageEnum), index=True)
    answers: Mapped[Dict[str, str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strengths: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    challenges: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    emotional_triggers: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    logical_patterns: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    current_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_steps: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    emotional_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resistance_points: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    recommended_stream: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stream_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    user: Mapped["User"] = relationship(back_populates="diagnostic_results")

    def __repr__(self):
        return f"<DiagnosticResult(user_id={self.user_id}, psychotype={self.psychotype}, stage={self.journey_stage})>"

class DiagnosticQuestion(Base):
    __tablename__ = "diagnostic_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Dict[str, str]] = mapped_column(JSON, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    emotional_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logical_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<DiagnosticQuestion(id={self.id}, text={self.text[:50]}...)>"

class UserSession(Base):
    """Модель для сохранения сессий бота (диагностика, провокативная сессия)"""
    __tablename__ = "user_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True, nullable=False)
    session_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, doc="Тип сессии: provocative, diagnostic, journey")
    state: Mapped[str] = mapped_column(String(50), nullable=True, doc="Текущее состояние FSM")
    conversation_history: Mapped[List[Dict[str, str]]] = mapped_column(
        JSON, nullable=False, default=list, doc="История диалога: [{'role': 'user'|'assistant', 'content': '...'}]"
    )
    identified_patterns: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, doc="Выявленные паттерны")
    core_issue: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Корневая проблема")
    question_count: Mapped[int] = mapped_column(Integer, default=0, doc="Количество вопросов в сессии")
    metaphysical_profile: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, doc="Метафизический профиль из сессии")
    core_trauma: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, doc="Корневая травма")
    session_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, doc="Дополнительные данные сессии")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, doc="Активна ли сессия")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True, doc="Дата завершения сессии")
    
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, type={self.session_type}, active={self.is_active})>"


class JourneyProgress(Base):
    __tablename__ = "journey_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    
    # Прогресс по этапам
    current_stage: Mapped[JourneyStageEnum] = mapped_column(SQLEnum(JourneyStageEnum))
    completed_stages: Mapped[Optional[List[JourneyStageEnum]]] = mapped_column(JSON)  # Список завершенных этапов
    stage_start_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))  # Время начала текущего этапа
    
    # Метрики вовлеченности
    total_interactions: Mapped[int] = mapped_column(Integer, default=0)
    emotional_responses: Mapped[Optional[List[str]]] = mapped_column(JSON)  # Записанные эмоциональные реакции
    logical_patterns_broken: Mapped[Optional[List[str]]] = mapped_column(JSON)  # Разрушенные логические паттерны
    
    # Связи
    user: Mapped["User"] = relationship(back_populates="journey_progress")

    def __repr__(self):
        return f"<JourneyProgress(id={self.id}, user_id={self.user_id}, current_stage={self.current_stage})>"


class TriggerTypeEnum(enum.Enum):
    """Типы проактивных триггеров"""
    INACTIVITY_24H = "inactivity_24h"
    MILESTONE_COMPLETED = "milestone_completed"
    PATTERN_DETECTED = "pattern_detected"
    MORNING_CHECK = "morning_check"
    STAGE_TRANSITION = "stage_transition"


class ProactiveTrigger(Base):
    """Модель для проактивных триггеров"""
    __tablename__ = "proactive_triggers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    trigger_type: Mapped[TriggerTypeEnum] = mapped_column(SQLEnum(TriggerTypeEnum), index=True)
    scheduled_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    executed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    message_sent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    executed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<ProactiveTrigger(id={self.id}, user_id={self.user_id}, type={self.trigger_type}, executed={self.executed})>"


class InteractionTypeEnum(enum.Enum):
    """Типы взаимодействий пользователя"""
    MESSAGE = "message"
    BUTTON_CLICK = "button_click"
    QUICK_REPLY = "quick_reply"
    COMMAND = "command"


class UserInteraction(Base):
    """Модель для трекинга взаимодействий пользователя"""
    __tablename__ = "user_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    interaction_type: Mapped[InteractionTypeEnum] = mapped_column(SQLEnum(InteractionTypeEnum))
    content: Mapped[str] = mapped_column(Text)
    journey_stage: Mapped[Optional[JourneyStageEnum]] = mapped_column(SQLEnum(JourneyStageEnum), nullable=True, index=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)
    interaction_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, doc="Дополнительные метаданные (длина сообщения, время ответа, etc.)")

    def __repr__(self):
        return f"<UserInteraction(id={self.id}, user_id={self.user_id}, type={self.interaction_type}, timestamp={self.timestamp})>"


class ProactivityConfig(Base):
    """Модель для конфигурации проактивности"""
    __tablename__ = "proactivity_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    max_messages_per_day: Mapped[int] = mapped_column(Integer, default=2)
    time_window_start: Mapped[datetime.time] = mapped_column(DateTime(timezone=False), default=datetime.time(8, 0))
    time_window_end: Mapped[datetime.time] = mapped_column(DateTime(timezone=False), default=datetime.time(22, 0))
    enabled_triggers: Mapped[List[str]] = mapped_column(JSON, default=list, doc="Список включённых типов триггеров")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ProactivityConfig(id={self.id}, max_messages={self.max_messages_per_day}, window={self.time_window_start}-{self.time_window_end})>"
