-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260527_backfill_request_log_provider.py
-- revision: 20260527_bfrlp
-- down_revision: 20260527_api_bases
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

UPDATE gateway_request_logs AS grl
    SET provider = pc.provider
    FROM provider_credentials AS pc
    WHERE grl.provider IS NULL
      AND grl.credential_id = pc.id
      AND pc.provider IS NOT NULL;
UPDATE gateway_request_logs AS grl
    SET provider = spc.provider
    FROM system_provider_credentials AS spc
    WHERE grl.provider IS NULL
      AND grl.credential_id = spc.id
      AND spc.provider IS NOT NULL;
UPDATE gateway_request_logs AS grl
    SET provider = gm.provider
    FROM gateway_models AS gm
    WHERE grl.provider IS NULL
      AND grl.deployment_gateway_model_id = gm.id
      AND gm.provider IS NOT NULL;
UPDATE gateway_request_logs AS grl
    SET provider = sgm.provider
    FROM system_gateway_models AS sgm
    WHERE grl.provider IS NULL
      AND grl.deployment_gateway_model_id = sgm.id
      AND sgm.provider IS NOT NULL;
UPDATE gateway_request_logs
    SET provider = CASE split_part(real_model, '/', 1)
        WHEN 'zai' THEN 'zhipuai'
        WHEN 'anthropic' THEN 'anthropic'
        WHEN 'dashscope' THEN 'dashscope'
        WHEN 'deepseek' THEN 'deepseek'
        WHEN 'volcengine' THEN 'volcengine'
        WHEN 'openai' THEN 'openai'
        ELSE provider
    END
    WHERE provider IS NULL
      AND real_model IS NOT NULL
      AND position('/' IN real_model) > 0
      AND split_part(real_model, '/', 1) IN (
          'zai', 'anthropic', 'dashscope', 'deepseek', 'volcengine', 'openai'
      );
