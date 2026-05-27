-- provider_credentials: track team credential creator for member-private access control

ALTER TABLE provider_credentials
    ADD COLUMN IF NOT EXISTS created_by_user_id UUID NULL;

COMMENT ON COLUMN provider_credentials.created_by_user_id IS
    'Team-scope credential creator (refs users.id, no DB FK); NULL = legacy shared admin-managed';

CREATE INDEX IF NOT EXISTS ix_provider_credentials_tenant_creator
    ON provider_credentials (tenant_id, created_by_user_id)
    WHERE tenant_id IS NOT NULL;
