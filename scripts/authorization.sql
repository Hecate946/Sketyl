CREATE TABLE IF NOT EXISTS spotify_auth (
    user_id TEXT PRIMARY KEY,
    token_info JSONB DEFAULT '{}'::JSONB
);
CREATE INDEX IF NOT EXISTS token_idx ON spotify_auth(user_id, token_info);