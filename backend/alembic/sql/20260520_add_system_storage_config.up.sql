-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260520_add_system_storage_config.py
-- revision: 20260520_ssc
-- down_revision: 20260520_grlc
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE system_storage_config (
    id UUID NOT NULL, 
    storage_type VARCHAR(20) DEFAULT 'local' NOT NULL, 
    local_storage_path VARCHAR(500), 
    local_serve_prefix VARCHAR(200) DEFAULT '/api/v1/listing-studio/images', 
    s3_bucket VARCHAR(200), 
    s3_region VARCHAR(50), 
    s3_endpoint_url VARCHAR(500), 
    s3_access_key VARCHAR(200), 
    s3_secret_key_encrypted TEXT, 
    s3_public_base_url VARCHAR(500), 
    image_upload_max_bytes INTEGER DEFAULT '10485760' NOT NULL, 
    public_access BOOLEAN DEFAULT 'true' NOT NULL, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    updated_by UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);
INSERT INTO system_storage_config (
                id, storage_type, local_storage_path, local_serve_prefix,
                image_upload_max_bytes, public_access, is_active
            )
            SELECT
                gen_random_uuid(), 'local', './data/storage/images',
                '/api/v1/listing-studio/images', 10485760, true, true
            WHERE NOT EXISTS (SELECT 1 FROM system_storage_config);
