-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260614_normalize_openai_real_model_prefix.py
-- revision: 20260614_oaipfx
-- down_revision: 20260614_gmcbu
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

UPDATE gateway_models
    SET real_model = substring(real_model from 8)
    WHERE real_model LIKE 'openai/%%';
UPDATE gateway_models
    SET real_model = substring(real_model from 11)
    WHERE real_model LIKE 'anthropic/%%';
UPDATE gateway_models
    SET real_model = substring(real_model from 11)
    WHERE real_model LIKE 'dashscope/%%';
UPDATE gateway_models
    SET real_model = substring(real_model from 10)
    WHERE real_model LIKE 'deepseek/%%';
UPDATE gateway_models
    SET real_model = substring(real_model from 12)
    WHERE real_model LIKE 'volcengine/%%';
UPDATE gateway_models
    SET real_model = substring(real_model from 10)
    WHERE real_model LIKE 'moonshot/%%';
UPDATE gateway_models
    SET real_model = substring(real_model from 5)
    WHERE real_model LIKE 'zai/%%';
UPDATE system_gateway_models
    SET real_model = substring(real_model from 8)
    WHERE real_model LIKE 'openai/%%';
UPDATE system_gateway_models
    SET real_model = substring(real_model from 11)
    WHERE real_model LIKE 'anthropic/%%';
UPDATE system_gateway_models
    SET real_model = substring(real_model from 11)
    WHERE real_model LIKE 'dashscope/%%';
UPDATE system_gateway_models
    SET real_model = substring(real_model from 10)
    WHERE real_model LIKE 'deepseek/%%';
UPDATE system_gateway_models
    SET real_model = substring(real_model from 12)
    WHERE real_model LIKE 'volcengine/%%';
UPDATE system_gateway_models
    SET real_model = substring(real_model from 10)
    WHERE real_model LIKE 'moonshot/%%';
UPDATE system_gateway_models
    SET real_model = substring(real_model from 5)
    WHERE real_model LIKE 'zai/%%';
