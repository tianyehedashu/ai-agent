-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260617_vkey_team_grants.py
-- revision: 20260617_vktg
-- down_revision: 20260616_dppi
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE gateway_virtual_key_team_grants (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    vkey_id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    granted_by_user_id UUID NOT NULL, 
    is_self BOOLEAN DEFAULT 'false' NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    revoked_reason VARCHAR(40), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);
CREATE INDEX ix_gateway_virtual_key_team_grants_granted_by_user_id ON gateway_virtual_key_team_grants (granted_by_user_id);
CREATE INDEX ix_gateway_virtual_key_team_grants_tenant_id ON gateway_virtual_key_team_grants (tenant_id);
CREATE INDEX ix_gateway_virtual_key_team_grants_vkey_id ON gateway_virtual_key_team_grants (vkey_id);
INSERT INTO gateway_virtual_key_team_grants (id, vkey_id, tenant_id, is_active, granted_by_user_id, is_self, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            v.id,
            v.tenant_id,
            TRUE,
            COALESCE(v.created_by_user_id, '00000000-0000-0000-0000-000000000000'::uuid),
            TRUE,
            NOW(),
            NOW()
        FROM gateway_virtual_keys v
        WHERE v.is_active = TRUE;
CREATE UNIQUE INDEX uq_vkey_team_grants_active
        ON gateway_virtual_key_team_grants (vkey_id, tenant_id)
        WHERE is_active = TRUE;
CREATE INDEX ix_vkey_team_grants_vkey_active
        ON gateway_virtual_key_team_grants (vkey_id)
        WHERE is_active = TRUE;
CREATE INDEX ix_vkey_team_grants_user_tenant_active
        ON gateway_virtual_key_team_grants (granted_by_user_id, tenant_id)
        WHERE is_active = TRUE;
