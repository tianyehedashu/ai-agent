-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260614_gateway_models_created_by_user_id.py
-- revision: 20260614_gmcbu
-- down_revision: 20260613_cct
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_models ADD COLUMN created_by_user_id UUID;
COMMENT ON COLUMN gateway_models.created_by_user_id IS '������ģ�͵��û� ID��refs users.id���� DB FK��';
CREATE INDEX ix_gateway_models_created_by_user_id ON gateway_models (created_by_user_id);
