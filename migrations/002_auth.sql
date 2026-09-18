CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    roles JSONB NOT NULL DEFAULT '["user"]',
    tenant_id TEXT NOT NULL DEFAULT 'default',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (username)
);

CREATE INDEX IF NOT EXISTS idx_users_tenant_id
    ON users (tenant_id);