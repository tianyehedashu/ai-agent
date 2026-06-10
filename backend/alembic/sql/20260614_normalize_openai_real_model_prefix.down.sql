-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260614_normalize_openai_real_model_prefix.py
-- revision: 20260614_oaipfx
-- down_revision: 20260614_gmcbu
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

UPDATE gateway_models
    SET real_model = 'openai/' || real_model
    WHERE provider = 'openai'
      AND real_model NOT LIKE '%%/%%';
UPDATE gateway_models
    SET real_model = 'anthropic/' || real_model
    WHERE provider = 'anthropic'
      AND real_model NOT LIKE '%%/%%';
UPDATE gateway_models
    SET real_model = 'dashscope/' || real_model
    WHERE provider = 'dashscope'
      AND real_model NOT LIKE '%%/%%';
UPDATE gateway_models
    SET real_model = 'deepseek/' || real_model
    WHERE provider = 'deepseek'
      AND real_model NOT LIKE '%%/%%';
UPDATE gateway_models
    SET real_model = 'volcengine/' || real_model
    WHERE provider = 'volcengine'
      AND real_model NOT LIKE '%%/%%';
UPDATE gateway_models
    SET real_model = 'moonshot/' || real_model
    WHERE provider = 'moonshot'
      AND real_model NOT LIKE '%%/%%';
UPDATE gateway_models
    SET real_model = 'zai/' || real_model
    WHERE provider = 'zhipuai'
      AND real_model NOT LIKE '%%/%%';
UPDATE system_gateway_models
    SET real_model = 'openai/' || real_model
    WHERE provider = 'openai'
      AND real_model NOT LIKE '%%/%%';
UPDATE system_gateway_models
    SET real_model = 'anthropic/' || real_model
    WHERE provider = 'anthropic'
      AND real_model NOT LIKE '%%/%%';
UPDATE system_gateway_models
    SET real_model = 'dashscope/' || real_model
    WHERE provider = 'dashscope'
      AND real_model NOT LIKE '%%/%%';
UPDATE system_gateway_models
    SET real_model = 'deepseek/' || real_model
    WHERE provider = 'deepseek'
      AND real_model NOT LIKE '%%/%%';
UPDATE system_gateway_models
    SET real_model = 'volcengine/' || real_model
    WHERE provider = 'volcengine'
      AND real_model NOT LIKE '%%/%%';
UPDATE system_gateway_models
    SET real_model = 'moonshot/' || real_model
    WHERE provider = 'moonshot'
      AND real_model NOT LIKE '%%/%%';
UPDATE system_gateway_models
    SET real_model = 'zai/' || real_model
    WHERE provider = 'zhipuai'
      AND real_model NOT LIKE '%%/%%';
