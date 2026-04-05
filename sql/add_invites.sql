CREATE TABLE IF NOT EXISTS invites (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    used_by_clerk_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_invites_email
ON invites (email);

CREATE INDEX IF NOT EXISTS ix_invites_is_active
ON invites (is_active);

CREATE INDEX IF NOT EXISTS ix_invites_used_by_clerk_id
ON invites (used_by_clerk_id);
