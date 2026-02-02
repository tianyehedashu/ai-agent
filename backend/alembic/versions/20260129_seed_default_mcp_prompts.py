"""seed_default_mcp_prompts

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2026-01-29

为 llm-server 插入 2 个默认 Prompt：总结、翻译。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "r0s1t2u3v4w5"
down_revision: str | None = "q9r0s1t2u3v4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# JSON 用绑定参数传入，避免 SQL 中的 "true" 被解析为绑定占位符
ARGS_SUMMARIZE = '[{"name":"content","description":"要总结的文本","required":true}]'
ARGS_TRANSLATE = '[{"name":"text","description":"要翻译的文本","required":true},{"name":"target_language","description":"目标语言，如：英文、中文","required":true}]'


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO mcp_dynamic_prompts
              (id, server_kind, server_id, prompt_key, title, description, arguments_schema, template, enabled, created_at, updated_at)
            VALUES
              (gen_random_uuid(), 'streamable_http', 'llm-server', 'summarize', '总结', '总结给定文本内容', CAST(:args1 AS jsonb), '请总结以下内容：\n\n{{content}}', true, now(), now()),
              (gen_random_uuid(), 'streamable_http', 'llm-server', 'translate', '翻译', '将文本翻译成目标语言', CAST(:args2 AS jsonb), '请将以下内容翻译成{{target_language}}：\n\n{{text}}', true, now(), now())
            ON CONFLICT (server_kind, server_id, prompt_key) DO NOTHING
            """
        ),
        {"args1": ARGS_SUMMARIZE, "args2": ARGS_TRANSLATE},
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM mcp_dynamic_prompts
        WHERE server_kind = 'streamable_http' AND server_id = 'llm-server'
          AND prompt_key IN ('summarize', 'translate')
        """
    )
