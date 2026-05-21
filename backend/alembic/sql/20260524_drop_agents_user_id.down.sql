-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260524_drop_agents_user_id.py
-- revision: 20260524_dau
-- down_revision: 20260523_sat
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE agents ADD COLUMN user_id UUID;
UPDATE agents a
        SET user_id = t.owner_user_id
        FROM gateway_teams t
        WHERE a.tenant_id = t.id
          AND t.kind = 'personal'
          AND t.owner_user_id IS NOT NULL;
ALTER TABLE agents ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE agents ADD CONSTRAINT agents_user_id_fkey FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;
CREATE INDEX ix_agents_user_id ON agents (user_id);
