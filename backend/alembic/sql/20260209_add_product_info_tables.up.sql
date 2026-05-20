-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260209_add_product_info_tables.py
-- revision: 20260209_pi
-- down_revision: 20260205_vendor_id
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE product_info_jobs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID, 
    anonymous_user_id VARCHAR(100), 
    session_id UUID, 
    title VARCHAR(200), 
    status VARCHAR(20) DEFAULT 'draft' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE SET NULL
);
COMMENT ON COLUMN product_info_jobs.anonymous_user_id IS '�����û�ID';
COMMENT ON COLUMN product_info_jobs.session_id IS '�����ỰID';
COMMENT ON COLUMN product_info_jobs.title IS '�������';
COMMENT ON COLUMN product_info_jobs.status IS 'draft, running, completed, failed, partial';
CREATE INDEX ix_product_info_jobs_user_id ON product_info_jobs (user_id);
CREATE INDEX ix_product_info_jobs_anonymous_user_id ON product_info_jobs (anonymous_user_id);
CREATE INDEX ix_product_info_jobs_session_id ON product_info_jobs (session_id);
CREATE INDEX ix_product_info_jobs_status ON product_info_jobs (status);
CREATE TABLE product_info_job_steps (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    job_id UUID NOT NULL, 
    sort_order INTEGER NOT NULL, 
    capability_id VARCHAR(50) NOT NULL, 
    input_snapshot JSONB, 
    output_snapshot JSONB, 
    prompt_used TEXT, 
    prompt_template_id UUID, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    error_message TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES product_info_jobs (id) ON DELETE CASCADE
);
COMMENT ON COLUMN product_info_job_steps.sort_order IS '����˳�� 1,2,3...';
COMMENT ON COLUMN product_info_job_steps.capability_id IS 'image_analysis, product_link_analysis, ...';
COMMENT ON COLUMN product_info_job_steps.input_snapshot IS '����ִ��ʱ����������';
COMMENT ON COLUMN product_info_job_steps.output_snapshot IS '����ִ�н��';
CREATE INDEX ix_product_info_job_steps_job_id ON product_info_job_steps (job_id);
CREATE INDEX ix_product_info_job_steps_capability_id ON product_info_job_steps (capability_id);
CREATE INDEX ix_product_info_job_steps_status ON product_info_job_steps (status);
CREATE TABLE product_info_prompt_templates (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID, 
    anonymous_user_id VARCHAR(100), 
    capability_id VARCHAR(50) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    content TEXT, 
    prompts JSONB, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
COMMENT ON COLUMN product_info_prompt_templates.capability_id IS 'image_analysis, ...';
COMMENT ON COLUMN product_info_prompt_templates.name IS 'ģ������';
COMMENT ON COLUMN product_info_prompt_templates.prompts IS '8 ����ʾ�ʣ��� image_gen_prompts ��';
CREATE INDEX ix_product_info_prompt_templates_user_id ON product_info_prompt_templates (user_id);
CREATE INDEX ix_product_info_prompt_templates_anonymous_user_id ON product_info_prompt_templates (anonymous_user_id);
CREATE INDEX ix_product_info_prompt_templates_capability_id ON product_info_prompt_templates (capability_id);
CREATE TABLE product_image_gen_tasks (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID, 
    anonymous_user_id VARCHAR(100), 
    job_id UUID, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    prompts JSONB DEFAULT '[]'::jsonb NOT NULL, 
    result_images JSONB, 
    error_message VARCHAR(500), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES product_info_jobs (id) ON DELETE SET NULL
);
COMMENT ON COLUMN product_image_gen_tasks.job_id IS '�����Ĳ�Ʒ��Ϣ����';
COMMENT ON COLUMN product_image_gen_tasks.prompts IS '8 �� { slot, prompt, model?, size? }';
COMMENT ON COLUMN product_image_gen_tasks.result_images IS '8 �� { slot, url }';
CREATE INDEX ix_product_image_gen_tasks_user_id ON product_image_gen_tasks (user_id);
CREATE INDEX ix_product_image_gen_tasks_anonymous_user_id ON product_image_gen_tasks (anonymous_user_id);
CREATE INDEX ix_product_image_gen_tasks_job_id ON product_image_gen_tasks (job_id);
CREATE INDEX ix_product_image_gen_tasks_status ON product_image_gen_tasks (status);
