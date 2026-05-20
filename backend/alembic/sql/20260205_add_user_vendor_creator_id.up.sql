-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260205_add_user_vendor_creator_id.py
-- revision: 20260205_vendor_id
-- down_revision: s3ss_v1d_cnt
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE users ADD COLUMN vendor_creator_id INTEGER;
COMMENT ON COLUMN users.vendor_creator_id IS '����ϵͳ�����û� ID���� GIIKIN creator_id��';
