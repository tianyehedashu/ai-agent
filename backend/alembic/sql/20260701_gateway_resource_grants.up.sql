-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260701_gateway_resource_grants.py
-- revision: 20260701_grg
-- down_revision: 20260630_socp
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE gateway_resource_grants (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    owner_user_id UUID NOT NULL, 
    subject_kind VARCHAR(20) NOT NULL, 
    subject_id UUID NOT NULL, 
    target_team_id UUID NOT NULL, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    note TEXT, 
    granted_by UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_gateway_resource_grants_subject_target UNIQUE (subject_kind, subject_id, target_team_id)
);
CREATE INDEX ix_gateway_resource_grants_owner_user_id ON gateway_resource_grants (owner_user_id);
CREATE INDEX ix_gateway_resource_grants_subject ON gateway_resource_grants (subject_kind, subject_id);
CREATE INDEX ix_gateway_resource_grants_target_enabled
        ON gateway_resource_grants (target_team_id, enabled)
        WHERE enabled IS TRUE;
ALTER TABLE gateway_request_logs ADD COLUMN resource_owner_user_id UUID;
ALTER TABLE gateway_metrics_hourly ADD COLUMN resource_owner_user_id UUID;
CREATE INDEX ix_gateway_request_logs_resource_owner_time
        ON gateway_request_logs (resource_owner_user_id, created_at)
        WHERE resource_owner_user_id IS NOT NULL;
