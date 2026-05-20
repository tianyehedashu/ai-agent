-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260515_api_key_gateway_grants.py
-- revision: 20260515_akgg
-- down_revision: 20260514_gld
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE api_key_gateway_grants (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    api_key_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    team_id UUID NOT NULL, 
    allowed_models VARCHAR(200)[] DEFAULT '{}'::character varying[] NOT NULL, 
    allowed_capabilities VARCHAR(40)[] DEFAULT '{}'::character varying[] NOT NULL, 
    rpm_limit INTEGER, 
    tpm_limit INTEGER, 
    store_full_messages BOOLEAN DEFAULT false NOT NULL, 
    guardrail_enabled BOOLEAN DEFAULT true NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_api_key_gateway_grants_key_team UNIQUE (api_key_id, team_id)
);
CREATE INDEX ix_api_key_gateway_grants_api_key_id ON api_key_gateway_grants (api_key_id);
CREATE INDEX ix_api_key_gateway_grants_user_id ON api_key_gateway_grants (user_id);
CREATE INDEX ix_api_key_gateway_grants_team_id ON api_key_gateway_grants (team_id);
CREATE INDEX ix_api_key_gateway_grants_is_active ON api_key_gateway_grants (is_active);
CREATE INDEX ix_api_key_gateway_grants_user_team ON api_key_gateway_grants (user_id, team_id);
INSERT INTO api_key_gateway_grants (
            api_key_id,
            user_id,
            team_id,
            allowed_models,
            allowed_capabilities,
            store_full_messages,
            guardrail_enabled,
            is_active
        )
        SELECT
            ak.id,
            ak.user_id,
            t.id,
            '{}'::character varying[],
            '{}'::character varying[],
            false,
            true,
            true
        FROM api_keys ak
        JOIN gateway_teams t
            ON t.owner_user_id = ak.user_id
           AND t.kind = 'personal'
           AND t.is_active = true
        WHERE ak.scopes @> ARRAY['gateway:proxy']::character varying[]
        ON CONFLICT ON CONSTRAINT uq_api_key_gateway_grants_key_team DO NOTHING;
