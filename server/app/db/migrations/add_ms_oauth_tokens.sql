-- Migration: add_ms_oauth_tokens
-- Adds per-user MS OAuth delegated token storage

CREATE TABLE IF NOT EXISTS ms_oauth_tokens (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ms_user_id       VARCHAR(255),
    ms_email         VARCHAR(255),
    access_token     TEXT NOT NULL,       -- Fernet-encrypted
    refresh_token    TEXT NOT NULL,       -- Fernet-encrypted
    token_expires_at TIMESTAMPTZ NOT NULL,
    scopes           TEXT,                -- space-separated
    connected_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_ms_oauth_tokens_user_id
    ON ms_oauth_tokens(user_id);
