-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260129_seed_default_mcp_prompts.py
-- revision: r0s1t2u3v4w5
-- down_revision: q9r0s1t2u3v4
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

INSERT INTO mcp_dynamic_prompts
              (id, server_kind, server_id, prompt_key, title, description, arguments_schema, template, enabled, created_at, updated_at)
            VALUES
              (gen_random_uuid(), 'streamable_http', 'llm-server', 'summarize', '�ܽ�', '�ܽ�����ı�����', CAST(NULL AS jsonb), '���ܽ��������ݣ�
{{content}}', true, now(), now()),
              (gen_random_uuid(), 'streamable_http', 'llm-server', 'translate', '����', '���ı������Ŀ������', CAST(NULL AS jsonb), '�뽫�������ݷ����{{target_language}}��
{{text}}', true, now(), now())
            ON CONFLICT (server_kind, server_id, prompt_key) DO NOTHING;
