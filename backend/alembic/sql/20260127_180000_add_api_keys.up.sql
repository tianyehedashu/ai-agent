-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260127_180000_add_api_keys.py
-- revision: c1d2e3f4g5h6
-- down_revision: b9c4d5e6f8g9
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE api_keys (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID NOT NULL, 
    key_hash VARCHAR(255) NOT NULL, 
    key_prefix VARCHAR(10) NOT NULL, 
    key_id VARCHAR(16) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    description TEXT, 
    scopes VARCHAR[] NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    last_used_at TIMESTAMP WITH TIME ZONE, 
    usage_count INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (key_hash)
);
COMMENT ON COLUMN api_keys.user_id IS '�����û� ID';
COMMENT ON COLUMN api_keys.key_hash IS 'bcrypt ��ϣ��� API Key';
COMMENT ON COLUMN api_keys.key_prefix IS 'Key ǰ׺���� ''sk_''';
COMMENT ON COLUMN api_keys.key_id IS '�����ʶ����16�ַ�����������־ʶ��';
COMMENT ON COLUMN api_keys.name IS '�û��Զ�������';
COMMENT ON COLUMN api_keys.description IS '����';
COMMENT ON COLUMN api_keys.scopes IS 'Ȩ�޷�Χ����';
COMMENT ON COLUMN api_keys.expires_at IS '����ʱ�䣨���';
COMMENT ON COLUMN api_keys.is_active IS '�Ƿ񼤻�';
COMMENT ON COLUMN api_keys.last_used_at IS '���ʹ��ʱ��';
COMMENT ON COLUMN api_keys.usage_count IS 'ʹ�ô���';
CREATE INDEX ix_api_keys_user_id ON api_keys (user_id);
CREATE INDEX ix_api_keys_key_hash ON api_keys (key_hash);
CREATE INDEX ix_api_keys_key_id ON api_keys (key_id);
CREATE INDEX ix_api_keys_expires_at ON api_keys (expires_at);
CREATE INDEX ix_api_keys_is_active ON api_keys (is_active);
CREATE TABLE api_key_usage_logs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    api_key_id UUID NOT NULL, 
    endpoint VARCHAR(255) NOT NULL, 
    method VARCHAR(10) NOT NULL, 
    ip_address VARCHAR(45), 
    user_agent TEXT, 
    status_code INTEGER NOT NULL, 
    response_time_ms INTEGER, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);
COMMENT ON COLUMN api_key_usage_logs.api_key_id IS '������ API Key ID';
COMMENT ON COLUMN api_key_usage_logs.endpoint IS '����˵�';
COMMENT ON COLUMN api_key_usage_logs.method IS 'HTTP ����';
COMMENT ON COLUMN api_key_usage_logs.ip_address IS '�ͻ��� IP';
COMMENT ON COLUMN api_key_usage_logs.user_agent IS 'User-Agent';
COMMENT ON COLUMN api_key_usage_logs.status_code IS 'HTTP ״̬��';
COMMENT ON COLUMN api_key_usage_logs.response_time_ms IS '��Ӧʱ�䣨���룩';
CREATE INDEX ix_api_key_usage_logs_api_key_id ON api_key_usage_logs (api_key_id);
CREATE INDEX ix_api_key_usage_logs_created_at ON api_key_usage_logs (created_at);
