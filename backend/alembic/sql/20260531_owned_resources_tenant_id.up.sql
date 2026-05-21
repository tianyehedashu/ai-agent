-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260531_owned_resources_tenant_id.py
-- revision: 20260531_ort
-- down_revision: 20260530_dps_tenant
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE product_info_jobs ADD COLUMN tenant_id UUID;
CREATE INDEX ix_product_info_jobs_tenant_id ON product_info_jobs (tenant_id);
UPDATE product_info_jobs x
SET tenant_id = t.id
FROM gateway_teams t
WHERE x.user_id IS NOT NULL
  AND t.owner_user_id = x.user_id
  AND t.kind = 'personal'
  AND t.is_active = TRUE;
UPDATE product_info_jobs x
SET tenant_id = t.id
FROM users u
JOIN gateway_teams t ON t.owner_user_id = u.id
    AND t.kind = 'personal'
    AND t.is_active = TRUE
WHERE x.anonymous_user_id IS NOT NULL
  AND x.tenant_id IS NULL
  AND u.role = 'anonymous'
  AND u.settings->>'anonymous_cookie_id' = x.anonymous_user_id;
ALTER TABLE product_info_jobs ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE video_gen_tasks ADD COLUMN tenant_id UUID;
CREATE INDEX ix_video_gen_tasks_tenant_id ON video_gen_tasks (tenant_id);
UPDATE video_gen_tasks x
SET tenant_id = t.id
FROM gateway_teams t
WHERE x.user_id IS NOT NULL
  AND t.owner_user_id = x.user_id
  AND t.kind = 'personal'
  AND t.is_active = TRUE;
UPDATE video_gen_tasks x
SET tenant_id = t.id
FROM users u
JOIN gateway_teams t ON t.owner_user_id = u.id
    AND t.kind = 'personal'
    AND t.is_active = TRUE
WHERE x.anonymous_user_id IS NOT NULL
  AND x.tenant_id IS NULL
  AND u.role = 'anonymous'
  AND u.settings->>'anonymous_cookie_id' = x.anonymous_user_id;
ALTER TABLE video_gen_tasks ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE product_image_gen_tasks ADD COLUMN tenant_id UUID;
CREATE INDEX ix_product_image_gen_tasks_tenant_id ON product_image_gen_tasks (tenant_id);
UPDATE product_image_gen_tasks x
SET tenant_id = t.id
FROM gateway_teams t
WHERE x.user_id IS NOT NULL
  AND t.owner_user_id = x.user_id
  AND t.kind = 'personal'
  AND t.is_active = TRUE;
UPDATE product_image_gen_tasks x
SET tenant_id = t.id
FROM users u
JOIN gateway_teams t ON t.owner_user_id = u.id
    AND t.kind = 'personal'
    AND t.is_active = TRUE
WHERE x.anonymous_user_id IS NOT NULL
  AND x.tenant_id IS NULL
  AND u.role = 'anonymous'
  AND u.settings->>'anonymous_cookie_id' = x.anonymous_user_id;
ALTER TABLE product_image_gen_tasks ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE product_info_prompt_templates ADD COLUMN tenant_id UUID;
CREATE INDEX ix_product_info_prompt_templates_tenant_id ON product_info_prompt_templates (tenant_id);
UPDATE product_info_prompt_templates x
SET tenant_id = t.id
FROM gateway_teams t
WHERE x.user_id IS NOT NULL
  AND t.owner_user_id = x.user_id
  AND t.kind = 'personal'
  AND t.is_active = TRUE;
UPDATE product_info_prompt_templates x
SET tenant_id = t.id
FROM users u
JOIN gateway_teams t ON t.owner_user_id = u.id
    AND t.kind = 'personal'
    AND t.is_active = TRUE
WHERE x.anonymous_user_id IS NOT NULL
  AND x.tenant_id IS NULL
  AND u.role = 'anonymous'
  AND u.settings->>'anonymous_cookie_id' = x.anonymous_user_id;
ALTER TABLE product_info_prompt_templates ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE memories ADD COLUMN tenant_id UUID;
CREATE INDEX ix_memories_tenant_id ON memories (tenant_id);
UPDATE memories x
SET tenant_id = t.id
FROM gateway_teams t
WHERE x.user_id IS NOT NULL
  AND t.owner_user_id = x.user_id
  AND t.kind = 'personal'
  AND t.is_active = TRUE;
ALTER TABLE memories ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE api_keys ADD COLUMN tenant_id UUID;
CREATE INDEX ix_api_keys_tenant_id ON api_keys (tenant_id);
UPDATE api_keys x
        SET tenant_id = t.id
        FROM gateway_teams t
        WHERE t.owner_user_id = x.user_id
          AND t.kind = 'personal'
          AND t.is_active = TRUE;
ALTER TABLE api_keys ALTER COLUMN tenant_id SET NOT NULL;
CREATE TABLE system_mcp_servers (
    id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    display_name VARCHAR(200), 
    url VARCHAR(500) NOT NULL, 
    env_type VARCHAR(50) NOT NULL, 
    env_config JSONB DEFAULT '{}' NOT NULL, 
    template_id VARCHAR(50), 
    inherit_defaults BOOLEAN DEFAULT 'false' NOT NULL, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    connection_status VARCHAR(20), 
    last_connected_at VARCHAR(50), 
    last_error TEXT, 
    available_tools JSONB DEFAULT '{}' NOT NULL, 
    description TEXT, 
    category VARCHAR(50), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_system_mcp_servers_name ON system_mcp_servers (name);
INSERT INTO system_mcp_servers (
            id, name, display_name, url, env_type, env_config, template_id,
            inherit_defaults, enabled, connection_status, last_connected_at,
            last_error, available_tools, description, category, created_at, updated_at
        )
        SELECT
            id, name, display_name, url, env_type, env_config, template_id,
            inherit_defaults, enabled, connection_status, last_connected_at,
            last_error, available_tools, description, category, created_at, updated_at
        FROM mcp_servers
        WHERE scope = 'system' OR user_id IS NULL;
DELETE FROM mcp_servers WHERE scope = 'system' OR user_id IS NULL;
ALTER TABLE mcp_servers ADD COLUMN tenant_id UUID;
CREATE INDEX ix_mcp_servers_tenant_id ON mcp_servers (tenant_id);
UPDATE mcp_servers x
SET tenant_id = t.id
FROM gateway_teams t
WHERE x.user_id IS NOT NULL
  AND t.owner_user_id = x.user_id
  AND t.kind = 'personal'
  AND t.is_active = TRUE;
ALTER TABLE mcp_servers ALTER COLUMN tenant_id SET NOT NULL;
