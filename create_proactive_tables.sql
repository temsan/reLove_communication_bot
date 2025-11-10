-- Создание таблиц для проактивной системы

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
);

CREATE INDEX IF NOT EXISTS ix_proactive_triggers_user_id ON proactive_triggers(user_id);
CREATE INDEX IF NOT EXISTS ix_proactive_triggers_trigger_type ON proactive_triggers(trigger_type);
CREATE INDEX IF NOT EXISTS ix_proactive_triggers_scheduled_time ON proactive_triggers(scheduled_time);
CREATE INDEX IF NOT EXISTS ix_proactive_triggers_executed ON proactive_triggers(executed);

CREATE TABLE IF NOT EXISTS user_interactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    interaction_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    journey_stage VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    interaction_metadata JSONB
);

CREATE INDEX IF NOT EXISTS ix_user_interactions_user_id ON user_interactions(user_id);
CREATE INDEX IF NOT EXISTS ix_user_interactions_journey_stage ON user_interactions(journey_stage);
CREATE INDEX IF NOT EXISTS ix_user_interactions_timestamp ON user_interactions(timestamp);

CREATE TABLE IF NOT EXISTS proactivity_config (
    id SERIAL PRIMARY KEY,
    max_messages_per_day INTEGER DEFAULT 2,
    time_window_start TIME,
    time_window_end TIME,
    enabled_triggers JSONB,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Вставляем дефолтную конфигурацию
INSERT INTO proactivity_config (max_messages_per_day, time_window_start, time_window_end, enabled_triggers)
VALUES (2, '08:00:00', '22:00:00', '["inactivity_24h", "milestone_completed", "pattern_detected", "morning_check"]'::jsonb)
ON CONFLICT DO NOTHING;
