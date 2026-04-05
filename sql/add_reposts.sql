CREATE TABLE IF NOT EXISTS reposts (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_clerk_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_post_repost UNIQUE (post_id, user_clerk_id)
);

CREATE INDEX IF NOT EXISTS ix_reposts_post_id
ON reposts (post_id);

CREATE INDEX IF NOT EXISTS ix_reposts_user_clerk_id
ON reposts (user_clerk_id);
