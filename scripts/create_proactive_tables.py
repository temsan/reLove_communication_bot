"""
Скрипт для создания таблиц проактивной системы
"""
import asyncio
from sqlalchemy import text
from relove_bot.db.session import async_session


async def create_proactive_tables():
    """Создаёт таблицы для проактивной системы"""
    
    queries = [
        # Таблица проактивных триггеров
        """
        CREATE TABLE IF NOT EXISTS proactive_triggers (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id),
            trigger_type VARCHAR(50) NOT NULL,
            scheduled_time TIMESTAMP WITH TIME ZONE NOT NULL,
            executed BOOLEAN DEFAULT FALSE,
            message_sent TEXT,
            user_response TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            executed_at TIMESTAMP WITH TIME ZONE,
            error_message TEXT
        )
        """,
        
        # Индексы для proactive_triggers
        "CREATE INDEX IF NOT EXISTS ix_proactive_triggers_user_id ON proactive_triggers(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_proactive_triggers_trigger_type ON proactive_triggers(trigger_type)",
        "CREATE INDEX IF NOT EXISTS ix_proactive_triggers_scheduled_time ON proactive_triggers(scheduled_time)",
        "CREATE INDEX IF NOT EXISTS ix_proactive_triggers_executed ON proactive_triggers(executed)",
        
        # Таблица взаимодействий
        """
        CREATE TABLE IF NOT EXISTS user_interactions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id),
            interaction_type VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            journey_stage VARCHAR(100),
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            interaction_metadata JSONB
        )
        """,
        
        # Индексы для user_interactions
        "CREATE INDEX IF NOT EXISTS ix_user_interactions_user_id ON user_interactions(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_interactions_journey_stage ON user_interactions(journey_stage)",
        "CREATE INDEX IF NOT EXISTS ix_user_interactions_timestamp ON user_interactions(timestamp)",
        
        # Таблица конфигурации
        """
        CREATE TABLE IF NOT EXISTS proactivity_config (
            id SERIAL PRIMARY KEY,
            max_messages_per_day INTEGER DEFAULT 2,
            time_window_start TIME,
            time_window_end TIME,
            enabled_triggers JSONB,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """,
        
        # Вставка дефолтной конфигурации
        """
        INSERT INTO proactivity_config (max_messages_per_day, time_window_start, time_window_end, enabled_triggers)
        SELECT 2, '08:00:00'::time, '22:00:00'::time, '["inactivity_24h", "milestone_completed", "pattern_detected", "morning_check"]'::jsonb
        WHERE NOT EXISTS (SELECT 1 FROM proactivity_config LIMIT 1)
        """
    ]
    
    async with async_session() as session:
        for query in queries:
            try:
                await session.execute(text(query))
                await session.commit()
                print(f"✓ Executed: {query[:50]}...")
            except Exception as e:
                print(f"✗ Error: {e}")
                await session.rollback()
    
    print("\n✅ All tables created successfully!")


if __name__ == "__main__":
    asyncio.run(create_proactive_tables())
