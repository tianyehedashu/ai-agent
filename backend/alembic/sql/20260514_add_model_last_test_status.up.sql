-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260514_add_model_last_test_status.py
-- revision: 20260514_mts
-- down_revision: 20260514_upt
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE user_models ADD COLUMN last_test_status VARCHAR(20);
COMMENT ON COLUMN user_models.last_test_status IS '�ϴ���ͨ�Բ��Խ��: success / failed / NULL=δ���';
ALTER TABLE user_models ADD COLUMN last_tested_at TIMESTAMP WITH TIME ZONE;
COMMENT ON COLUMN user_models.last_tested_at IS '�ϴ���ͨ�Բ���ʱ��';
ALTER TABLE gateway_models ADD COLUMN last_test_status VARCHAR(20);
COMMENT ON COLUMN gateway_models.last_test_status IS '�ϴ���ͨ�Բ��Խ��: success / failed / NULL=δ���';
ALTER TABLE gateway_models ADD COLUMN last_tested_at TIMESTAMP WITH TIME ZONE;
COMMENT ON COLUMN gateway_models.last_tested_at IS '�ϴ���ͨ�Բ���ʱ��';
