-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260603_system_visibility_acl.py
-- revision: 20260603_svac
-- down_revision: 20260602_dafk
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE system_provider_credentials ADD COLUMN visibility VARCHAR(20) DEFAULT 'public' NOT NULL;
ALTER TABLE system_gateway_models ADD COLUMN visibility VARCHAR(20) DEFAULT 'inherit' NOT NULL;
CREATE TABLE system_gateway_grants (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    subject_kind VARCHAR(20) NOT NULL, 
    subject_id UUID NOT NULL, 
    target_kind VARCHAR(20) NOT NULL, 
    target_id UUID NOT NULL, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    note TEXT, 
    granted_by UUID NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_system_gateway_grants_subject_target UNIQUE (subject_kind, subject_id, target_kind, target_id)
);
CREATE INDEX ix_system_gateway_grants_subject ON system_gateway_grants (subject_kind, subject_id);
CREATE INDEX ix_system_gateway_grants_target ON system_gateway_grants (target_kind, target_id);
