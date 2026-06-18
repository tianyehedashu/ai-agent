-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260618_prune_orphan_provider_plans.py
-- revision: 20260618_pop
-- down_revision: 20260617_vktg
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DELETE FROM provider_plan_quotas
        WHERE plan_id IN (
SELECT p.id
FROM provider_plans p
WHERE p.real_model IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM gateway_models gm
      WHERE gm.credential_id = p.credential_id
        AND gm.real_model = p.real_model
  )
  AND NOT EXISTS (
      SELECT 1 FROM system_gateway_models sgm
      WHERE sgm.credential_id = p.credential_id
        AND sgm.real_model = p.real_model
  )
);
DELETE FROM provider_plans
        WHERE id IN (
SELECT p.id
FROM provider_plans p
WHERE p.real_model IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM gateway_models gm
      WHERE gm.credential_id = p.credential_id
        AND gm.real_model = p.real_model
  )
  AND NOT EXISTS (
      SELECT 1 FROM system_gateway_models sgm
      WHERE sgm.credential_id = p.credential_id
        AND sgm.real_model = p.real_model
  )
);
