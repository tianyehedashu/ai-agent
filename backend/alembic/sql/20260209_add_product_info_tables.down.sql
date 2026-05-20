-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260209_add_product_info_tables.py
-- revision: 20260209_pi
-- down_revision: 20260205_vendor_id
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP TABLE product_image_gen_tasks;
DROP TABLE product_info_prompt_templates;
DROP TABLE product_info_job_steps;
DROP TABLE product_info_jobs;
