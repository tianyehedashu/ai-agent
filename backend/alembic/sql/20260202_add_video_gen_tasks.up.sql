-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260202_add_video_gen_tasks.py
-- revision: v1d3o_g3n_t4sk
-- down_revision: r0s1t2u3v4w5
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE video_gen_tasks (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID, 
    anonymous_user_id VARCHAR(100), 
    session_id UUID, 
    workflow_id VARCHAR(100), 
    run_id VARCHAR(100), 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    prompt_text TEXT, 
    prompt_source VARCHAR(50), 
    reference_images JSONB DEFAULT '[]'::jsonb NOT NULL, 
    marketplace VARCHAR(10) DEFAULT 'jp' NOT NULL, 
    result JSONB, 
    error_message TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE SET NULL
);
COMMENT ON COLUMN video_gen_tasks.anonymous_user_id IS '�����û�ID������δ��¼�û�������';
COMMENT ON COLUMN video_gen_tasks.session_id IS '�����ĻỰID';
COMMENT ON COLUMN video_gen_tasks.workflow_id IS '���̷��ص� workflow_id';
COMMENT ON COLUMN video_gen_tasks.run_id IS '���̷��ص� run_id';
COMMENT ON COLUMN video_gen_tasks.status IS '����״̬: pending, running, completed, failed, cancelled';
COMMENT ON COLUMN video_gen_tasks.prompt_text IS '��������Ƶ������ʾ��';
COMMENT ON COLUMN video_gen_tasks.prompt_source IS '��ʾ����Դ: agent_generated, user_provided, template';
COMMENT ON COLUMN video_gen_tasks.reference_images IS '�ο�ͼƬ URL �б�';
COMMENT ON COLUMN video_gen_tasks.marketplace IS 'Ŀ��վ��: jp, us, de, uk, fr, it, es ��';
COMMENT ON COLUMN video_gen_tasks.result IS '���̷��ص������������ video_url �ȣ�';
COMMENT ON COLUMN video_gen_tasks.error_message IS '������Ϣ';
CREATE INDEX ix_video_gen_tasks_user_id ON video_gen_tasks (user_id);
CREATE INDEX ix_video_gen_tasks_anonymous_user_id ON video_gen_tasks (anonymous_user_id);
CREATE INDEX ix_video_gen_tasks_session_id ON video_gen_tasks (session_id);
CREATE INDEX ix_video_gen_tasks_workflow_id ON video_gen_tasks (workflow_id);
CREATE INDEX ix_video_gen_tasks_run_id ON video_gen_tasks (run_id);
CREATE INDEX ix_video_gen_tasks_status ON video_gen_tasks (status);
