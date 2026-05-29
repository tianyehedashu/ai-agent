-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260609_add_user_giikin_user_id.py
-- revision: 20260609_giikin_uid
-- down_revision: 20260608_cred_creator
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE users ADD COLUMN giikin_user_id VARCHAR(64);
COMMENT ON COLUMN users.giikin_user_id IS 'giikin 单点登录用户 ID（SSO 模式下经 HiGress 注入，JIT 映射键）';
CREATE UNIQUE INDEX ix_users_giikin_user_id ON users (giikin_user_id);
