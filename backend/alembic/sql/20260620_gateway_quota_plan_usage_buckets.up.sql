-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260620_gateway_quota_plan_usage_buckets.py
-- revision: 20260620_gqpub
-- down_revision: 20260619_tccb
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE gateway_quota_plan_usage_buckets (
    ns VARCHAR(16) NOT NULL, 
    plan_id UUID NOT NULL, 
    quota_id UUID NOT NULL, 
    window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
    tokens BIGINT DEFAULT '0' NOT NULL, 
    requests BIGINT DEFAULT '0' NOT NULL, 
    cost_usd NUMERIC(14, 6) DEFAULT '0' NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (ns, plan_id, quota_id, window_start)
);
