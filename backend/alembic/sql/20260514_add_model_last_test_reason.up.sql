-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260514_add_model_last_test_reason.py
-- revision: 20260514_mtr
-- down_revision: 20260514_mts
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE user_models ADD COLUMN last_test_reason TEXT;
COMMENT ON COLUMN user_models.last_test_reason IS '�ϴ���ͨ�Բ���˵����ʧ��ԭ��ȣ����ɹ�ʱΪ NULL';
ALTER TABLE gateway_models ADD COLUMN last_test_reason TEXT;
COMMENT ON COLUMN gateway_models.last_test_reason IS '�ϴ���ͨ�Բ���˵����ʧ��ԭ��ȣ����ɹ�ʱΪ NULL';
