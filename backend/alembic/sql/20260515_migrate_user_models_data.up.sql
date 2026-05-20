-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260515_migrate_user_models_data.py
-- revision: 20260515_um_data
-- down_revision: 20260515_gm_lum
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

INSERT INTO gateway_teams (
        id, name, slug, kind, owner_user_id, settings, is_active, created_at, updated_at
    )
    SELECT
        gen_random_uuid(), 'Personal',
        'personal-' || u.user_id::text,
        'personal', u.user_id, '{}'::jsonb, true, now(), now()
    FROM (SELECT DISTINCT user_id FROM user_models WHERE user_id IS NOT NULL) u
    WHERE NOT EXISTS (
        SELECT 1 FROM gateway_teams t
        WHERE t.owner_user_id = u.user_id
          AND t.kind = 'personal'
          AND t.is_active = true
    );
INSERT INTO gateway_team_members (
        id, team_id, user_id, role, created_at, updated_at
    )
    SELECT gen_random_uuid(), t.id, t.owner_user_id, 'owner', now(), now()
    FROM gateway_teams t
    WHERE t.kind = 'personal'
      AND t.is_active = true
      AND NOT EXISTS (
          SELECT 1 FROM gateway_team_members m
          WHERE m.team_id = t.id AND m.user_id = t.owner_user_id
      );
