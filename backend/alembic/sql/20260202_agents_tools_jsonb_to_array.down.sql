-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260202_agents_tools_jsonb_to_array.py
-- revision: a2b3c4d5e6f7
-- down_revision: v1d3o_g3n_t4sk
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE agents ALTER COLUMN tools DROP DEFAULT;
ALTER TABLE agents
        ALTER COLUMN tools TYPE JSONB
        USING to_jsonb(tools);
ALTER TABLE agents ALTER COLUMN tools TYPE JSONB;
ALTER TABLE agents ALTER COLUMN tools SET NOT NULL;
ALTER TABLE agents ALTER COLUMN tools SET DEFAULT '[]'::jsonb;
