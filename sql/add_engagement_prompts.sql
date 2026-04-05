CREATE TABLE IF NOT EXISTS engagement_prompts (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    suggested_tags TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_prompt_events (
    id SERIAL PRIMARY KEY,
    prompt_id INTEGER NOT NULL REFERENCES engagement_prompts(id) ON DELETE CASCADE,
    user_clerk_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_engagement_prompts_active_created
ON engagement_prompts (is_active, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_user_prompt_events_user_created
ON user_prompt_events (user_clerk_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_user_prompt_events_user_prompt_created
ON user_prompt_events (user_clerk_id, prompt_id, created_at DESC);
