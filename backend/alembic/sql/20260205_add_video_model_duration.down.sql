-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260205_add_video_model_duration.py
-- revision: v1d3o_m0d3l_dur
-- down_revision: a2b3c4d5e6f7
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE video_gen_tasks DROP COLUMN duration;
ALTER TABLE video_gen_tasks DROP COLUMN model;
