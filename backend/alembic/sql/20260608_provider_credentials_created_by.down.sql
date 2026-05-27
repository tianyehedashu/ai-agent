DROP INDEX IF EXISTS ix_provider_credentials_tenant_creator;

ALTER TABLE provider_credentials
    DROP COLUMN IF EXISTS created_by_user_id;
