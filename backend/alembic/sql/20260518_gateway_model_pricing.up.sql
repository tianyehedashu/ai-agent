-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260518_gateway_model_pricing.py
-- revision: 20260518_gmp
-- down_revision: 20260518_gpep
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE upstream_model_pricing (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    provider VARCHAR(50) NOT NULL, 
    upstream_model VARCHAR(200) NOT NULL, 
    capability VARCHAR(40) DEFAULT 'chat' NOT NULL, 
    input_cost_per_token NUMERIC(14, 10) NOT NULL, 
    output_cost_per_token NUMERIC(14, 10) NOT NULL, 
    cache_creation_input_token_cost NUMERIC(14, 10), 
    cache_read_input_token_cost NUMERIC(14, 10), 
    extra JSONB, 
    effective_from TIMESTAMP WITH TIME ZONE NOT NULL, 
    effective_to TIMESTAMP WITH TIME ZONE, 
    version INTEGER DEFAULT '1' NOT NULL, 
    source VARCHAR(32) DEFAULT 'manual' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_upstream_model_pricing_natural UNIQUE (provider, upstream_model, capability, effective_from)
);
CREATE INDEX ix_upstream_model_pricing_provider ON upstream_model_pricing (provider);
CREATE INDEX ix_upstream_model_pricing_upstream_model ON upstream_model_pricing (upstream_model);
CREATE INDEX ix_upstream_model_pricing_lookup ON upstream_model_pricing (provider, upstream_model, capability, effective_from, effective_to);
CREATE TABLE downstream_model_pricing (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    scope VARCHAR(32) NOT NULL, 
    scope_id UUID, 
    gateway_model_id UUID, 
    input_cost_per_token NUMERIC(14, 10), 
    output_cost_per_token NUMERIC(14, 10), 
    cache_creation_input_token_cost NUMERIC(14, 10), 
    cache_read_input_token_cost NUMERIC(14, 10), 
    per_request_usd NUMERIC(12, 6), 
    inheritance_strategy VARCHAR(16) DEFAULT 'manual' NOT NULL, 
    extra JSONB, 
    effective_from TIMESTAMP WITH TIME ZONE NOT NULL, 
    effective_to TIMESTAMP WITH TIME ZONE, 
    version INTEGER DEFAULT '1' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_downstream_model_pricing_natural UNIQUE (scope, scope_id, gateway_model_id, effective_from), 
    CONSTRAINT ck_downstream_pricing_strategy_columns CHECK ((inheritance_strategy = 'manual' AND input_cost_per_token IS NOT NULL AND output_cost_per_token IS NOT NULL) OR (inheritance_strategy = 'mirror' AND input_cost_per_token IS NULL AND output_cost_per_token IS NULL AND cache_creation_input_token_cost IS NULL AND cache_read_input_token_cost IS NULL)), 
    FOREIGN KEY(gateway_model_id) REFERENCES gateway_models (id) ON DELETE CASCADE
);
CREATE INDEX ix_downstream_model_pricing_scope_id ON downstream_model_pricing (scope_id);
CREATE INDEX ix_downstream_model_pricing_gateway_model_id ON downstream_model_pricing (gateway_model_id);
CREATE INDEX ix_downstream_model_pricing_lookup ON downstream_model_pricing (scope, scope_id, gateway_model_id, effective_from, effective_to);
ALTER TABLE gateway_request_logs ADD COLUMN revenue_usd NUMERIC(12, 6) DEFAULT '0' NOT NULL;
ALTER TABLE gateway_request_logs ADD COLUMN pricing_snapshot JSONB;
ALTER TABLE gateway_budgets ADD COLUMN soft_limit_usd NUMERIC(12, 4);
ALTER TABLE gateway_budgets ADD COLUMN max_parallel_requests INTEGER;
ALTER TABLE gateway_budgets ADD COLUMN budget_reset_at TIMESTAMP WITH TIME ZONE;
