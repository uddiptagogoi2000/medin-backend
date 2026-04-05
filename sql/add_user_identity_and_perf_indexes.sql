ALTER TABLE users
ADD COLUMN IF NOT EXISTS first_name TEXT,
ADD COLUMN IF NOT EXISTS last_name TEXT,
ADD COLUMN IF NOT EXISTS full_name TEXT,
ADD COLUMN IF NOT EXISTS avatar_url TEXT;

CREATE INDEX IF NOT EXISTS ix_posts_author_created_at
ON posts (author_clerk_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_posts_visibility_created_at
ON posts (visibility, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_likes_post_id
ON likes (post_id);

CREATE INDEX IF NOT EXISTS ix_likes_user_post
ON likes (user_clerk_id, post_id);

CREATE INDEX IF NOT EXISTS ix_comments_post_id
ON comments (post_id);

CREATE INDEX IF NOT EXISTS ix_comments_author_created_at
ON comments (author_clerk_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_reposts_user_post
ON reposts (user_clerk_id, post_id);

CREATE INDEX IF NOT EXISTS ix_follows_follower_following
ON follows (follower_clerk_id, following_clerk_id);

CREATE INDEX IF NOT EXISTS ix_follows_follower_created_at
ON follows (follower_clerk_id, created_at DESC);
