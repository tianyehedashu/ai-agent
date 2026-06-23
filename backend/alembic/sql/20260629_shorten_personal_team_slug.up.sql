-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260629_shorten_personal_team_slug.py
-- revision: 20260629_ptsl
-- down_revision: 20260622_grl_user_ix
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

UPDATE gateway_teams
        SET slug = 'personal-' || substr(replace(owner_user_id::text, '-', ''), 1, 8)
        WHERE kind = 'personal'
          AND slug = 'personal-' || owner_user_id::text;
