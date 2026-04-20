ALTER TABLE invites
ALTER COLUMN email DROP NOT NULL;

ALTER TABLE invites
ADD COLUMN IF NOT EXISTS token_hash TEXT UNIQUE;

ALTER TABLE invites
ADD COLUMN IF NOT EXISTS invite_type TEXT NOT NULL DEFAULT 'email';

ALTER TABLE invites
ADD COLUMN IF NOT EXISTS used_by_email TEXT;

ALTER TABLE invites
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

ALTER TABLE invites
ADD COLUMN IF NOT EXISTS used_at TIMESTAMPTZ;

ALTER TABLE invites
ADD COLUMN IF NOT EXISTS note TEXT;

UPDATE invites
SET invite_type = 'email'
WHERE invite_type IS NULL;

CREATE INDEX IF NOT EXISTS ix_invites_token_hash
ON invites (token_hash);

CREATE INDEX IF NOT EXISTS ix_invites_invite_type
ON invites (invite_type);

CREATE INDEX IF NOT EXISTS ix_invites_used_by_email
ON invites (used_by_email);

CREATE INDEX IF NOT EXISTS ix_invites_expires_at
ON invites (expires_at);
