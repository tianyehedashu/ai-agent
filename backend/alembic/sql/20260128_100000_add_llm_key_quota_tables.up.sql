-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260128_100000_add_llm_key_quota_tables.py
-- revision: g5h6i7j8k9l0
-- down_revision: f4g5h6i7j8k9
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE user_provider_configs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID NOT NULL, 
    provider VARCHAR(50) NOT NULL, 
    api_key TEXT NOT NULL, 
    api_base VARCHAR(255), 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_user_provider_config UNIQUE (user_id, provider)
);
CREATE INDEX ix_user_provider_configs_is_active ON user_provider_configs (is_active);
CREATE INDEX ix_user_provider_configs_provider ON user_provider_configs (provider);
CREATE INDEX ix_user_provider_configs_user_id ON user_provider_configs (user_id);
COMMENT ON COLUMN user_provider_configs.user_id IS '�����û� ID';
COMMENT ON COLUMN user_provider_configs.provider IS '�ṩ�̱�ʶ: openai, anthropic, dashscope, zhipuai, deepseek, volcengine';
COMMENT ON COLUMN user_provider_configs.api_key IS '���ܴ洢�� API Key';
COMMENT ON COLUMN user_provider_configs.api_base IS '�Զ��� API Base URL����ѡ��';
COMMENT ON COLUMN user_provider_configs.is_active IS '�Ƿ�����';
CREATE TABLE user_quotas (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID NOT NULL, 
    daily_text_requests INTEGER, 
    daily_image_requests INTEGER, 
    daily_embedding_requests INTEGER, 
    monthly_token_limit INTEGER, 
    current_daily_text INTEGER DEFAULT 0 NOT NULL, 
    current_daily_image INTEGER DEFAULT 0 NOT NULL, 
    current_daily_embedding INTEGER DEFAULT 0 NOT NULL, 
    current_monthly_tokens INTEGER DEFAULT 0 NOT NULL, 
    daily_reset_at TIMESTAMP WITH TIME ZONE, 
    monthly_reset_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_user_quotas_user_id ON user_quotas (user_id);
COMMENT ON COLUMN user_quotas.user_id IS '�����û� ID��һ��һ��';
COMMENT ON COLUMN user_quotas.daily_text_requests IS 'ÿ���ı����������ޣ�None ��ʾ�����ƣ�';
COMMENT ON COLUMN user_quotas.daily_image_requests IS 'ÿ��ͼ������������';
COMMENT ON COLUMN user_quotas.daily_embedding_requests IS 'ÿ�� Embedding ����������';
COMMENT ON COLUMN user_quotas.monthly_token_limit IS 'ÿ�� Token ����';
COMMENT ON COLUMN user_quotas.current_daily_text IS '��ǰÿ���ı�����������';
COMMENT ON COLUMN user_quotas.current_daily_image IS '��ǰÿ��ͼ������������';
COMMENT ON COLUMN user_quotas.current_daily_embedding IS '��ǰÿ�� Embedding ������';
COMMENT ON COLUMN user_quotas.current_monthly_tokens IS '��ǰÿ�� Token ������';
COMMENT ON COLUMN user_quotas.daily_reset_at IS 'ÿ������´�����ʱ��';
COMMENT ON COLUMN user_quotas.monthly_reset_at IS 'ÿ������´�����ʱ��';
CREATE TABLE quota_usage_logs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID NOT NULL, 
    capability VARCHAR(20) NOT NULL, 
    provider VARCHAR(50) NOT NULL, 
    model VARCHAR(100), 
    key_source VARCHAR(10) NOT NULL, 
    input_tokens INTEGER, 
    output_tokens INTEGER, 
    image_count INTEGER, 
    cost_estimate NUMERIC(10, 4), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);
CREATE INDEX ix_quota_usage_logs_user_id ON quota_usage_logs (user_id);
CREATE INDEX ix_quota_usage_logs_key_source ON quota_usage_logs (key_source);
CREATE INDEX ix_quota_usage_logs_capability ON quota_usage_logs (capability);
CREATE INDEX ix_quota_usage_logs_provider ON quota_usage_logs (provider);
COMMENT ON COLUMN quota_usage_logs.user_id IS '�û� ID';
COMMENT ON COLUMN quota_usage_logs.capability IS '��������: text, image, embedding';
COMMENT ON COLUMN quota_usage_logs.provider IS '�ṩ��: openai, anthropic, dashscope, etc.';
COMMENT ON COLUMN quota_usage_logs.model IS 'ģ������';
COMMENT ON COLUMN quota_usage_logs.key_source IS 'Key ��Դ: user �� system';
COMMENT ON COLUMN quota_usage_logs.input_tokens IS '���� Token ��';
COMMENT ON COLUMN quota_usage_logs.output_tokens IS '��� Token ��';
COMMENT ON COLUMN quota_usage_logs.image_count IS '����ͼ����';
COMMENT ON COLUMN quota_usage_logs.cost_estimate IS '������ã���Ԫ��';
COMMENT ON COLUMN quota_usage_logs.created_at IS '����ʱ��';
