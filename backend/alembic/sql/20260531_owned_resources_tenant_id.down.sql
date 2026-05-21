-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260531_owned_resources_tenant_id.py
-- revision: 20260531_ort
-- down_revision: 20260530_dps_tenant
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE mcp_servers DROP COLUMN tenant_id;
DROP TABLE system_mcp_servers;
DROP INDEX ix_api_keys_tenant_id;
ALTER TABLE api_keys DROP COLUMN tenant_id;
DROP INDEX ix_memories_tenant_id;
ALTER TABLE memories DROP COLUMN tenant_id;
DROP INDEX ix_product_info_prompt_templates_tenant_id;
ALTER TABLE product_info_prompt_templates DROP COLUMN tenant_id;
DROP INDEX ix_product_image_gen_tasks_tenant_id;
ALTER TABLE product_image_gen_tasks DROP COLUMN tenant_id;
DROP INDEX ix_video_gen_tasks_tenant_id;
ALTER TABLE video_gen_tasks DROP COLUMN tenant_id;
DROP INDEX ix_product_info_jobs_tenant_id;
ALTER TABLE product_info_jobs DROP COLUMN tenant_id;
