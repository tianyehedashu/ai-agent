-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic downgrade -1  （走 alembic/versions/*.py）
-- versions/20260601_drop_legacy_tenant_id_fks.py
-- revision: 20260601_dltif
-- down_revision: 20260531_ort
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_models
    ADD CONSTRAINT gateway_models_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES gateway_teams (id) ON DELETE CASCADE;
ALTER TABLE gateway_routes
    ADD CONSTRAINT gateway_routes_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES gateway_teams (id) ON DELETE CASCADE;
ALTER TABLE gateway_alert_rules
    ADD CONSTRAINT gateway_alert_rules_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES gateway_teams (id) ON DELETE CASCADE;
ALTER TABLE gateway_virtual_keys
    ADD CONSTRAINT gateway_virtual_keys_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES gateway_teams (id) ON DELETE CASCADE;
