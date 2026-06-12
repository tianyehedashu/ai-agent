-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用：uv run alembic upgrade head  （走 alembic/versions/*.py）
-- 方向：UPGRADE (up.sql)
--   up.sql   = 升级（填充 provider_credentials.created_by_user_id 为 NULL 的历史数据）
--   down.sql = 回滚（不执行回滚操作）
-- 说明：将团队凭据中 created_by_user_id 为 NULL 的记录，根据创建时的团队成员关系回填
-- =============================================================================

-- 修复团队凭据：根据最早的团队成员关系回填 created_by_user_id
-- 逻辑：选择团队中最早加入的管理员或成员作为创建者
UPDATE provider_credentials pc
SET created_by_user_id = (
    SELECT tm.user_id
    FROM team_members tm
    WHERE tm.team_id = pc.tenant_id
      AND tm.role IN ('admin', 'member')
    ORDER BY tm.created_at ASC
    LIMIT 1
)
WHERE pc.tenant_id IS NOT NULL
  AND pc.scope IS NULL
  AND pc.created_by_user_id IS NULL;

-- 输出修复结果
SELECT 
    '已修复 ' || COUNT(*) || ' 条团队凭据的 created_by_user_id' AS result
FROM provider_credentials
WHERE tenant_id IS NOT NULL
  AND scope IS NULL
  AND created_by_user_id IS NOT NULL;
