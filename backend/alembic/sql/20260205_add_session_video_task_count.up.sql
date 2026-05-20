-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260205_add_session_video_task_count.py
-- revision: s3ss_v1d_cnt
-- down_revision: v1d3o_m0d3l_dur
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE sessions ADD COLUMN video_task_count INTEGER DEFAULT '0' NOT NULL;
COMMENT ON COLUMN sessions.video_task_count IS '��Ƶ��������';
