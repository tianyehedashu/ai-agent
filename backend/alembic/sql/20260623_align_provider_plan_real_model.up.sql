-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260623_align_provider_plan_real_model.py
-- revision: 20260623_apprm
-- down_revision: 20260622_gqpub_uat
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

UPDATE provider_plans AS pp
        SET real_model = lower(pc.provider) || '/' || pp.real_model
        FROM provider_credentials AS pc
        WHERE pp.credential_id = pc.id
          AND pp.real_model IS NOT NULL
          AND strpos(pp.real_model, '/') = 0
          AND NOT EXISTS (
            SELECT 1 FROM (
    SELECT credential_id, real_model FROM gateway_models
    UNION ALL
    SELECT credential_id, real_model FROM system_gateway_models
) AS reg
            WHERE reg.credential_id = pp.credential_id
              AND reg.real_model = pp.real_model
          )
          AND EXISTS (
            SELECT 1 FROM (
    SELECT credential_id, real_model FROM gateway_models
    UNION ALL
    SELECT credential_id, real_model FROM system_gateway_models
) AS reg
            WHERE reg.credential_id = pp.credential_id
              AND reg.real_model = lower(pc.provider) || '/' || pp.real_model
          );
UPDATE provider_plans AS pp
        SET real_model = reg.real_model
        FROM (
    SELECT credential_id, real_model FROM gateway_models
    UNION ALL
    SELECT credential_id, real_model FROM system_gateway_models
) AS reg
        WHERE pp.credential_id = reg.credential_id
          AND pp.real_model IS NOT NULL
          AND pp.real_model <> reg.real_model
          AND lower(split_part(pp.real_model, '/', 2)) = lower(split_part(reg.real_model, '/', 2))
          AND NOT EXISTS (
            SELECT 1 FROM (
    SELECT credential_id, real_model FROM gateway_models
    UNION ALL
    SELECT credential_id, real_model FROM system_gateway_models
) AS exact
            WHERE exact.credential_id = pp.credential_id
              AND exact.real_model = pp.real_model
          );
UPDATE provider_plans AS pp
        SET real_model = sole.real_model
        FROM (
            SELECT reg.credential_id, min(reg.real_model) AS real_model
            FROM (
    SELECT credential_id, real_model FROM gateway_models
    UNION ALL
    SELECT credential_id, real_model FROM system_gateway_models
) AS reg
            GROUP BY reg.credential_id
            HAVING count(*) = 1
        ) AS sole
        WHERE pp.credential_id = sole.credential_id
          AND pp.real_model IS NOT NULL
          AND pp.real_model <> sole.real_model
          AND NOT EXISTS (
            SELECT 1 FROM (
    SELECT credential_id, real_model FROM gateway_models
    UNION ALL
    SELECT credential_id, real_model FROM system_gateway_models
) AS reg
            WHERE reg.credential_id = pp.credential_id
              AND reg.real_model = pp.real_model
          );
