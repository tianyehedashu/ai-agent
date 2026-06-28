"""reserved_team_slugs — 保留 team slug 列表（防止与 LiteLLM vendor prefix 冲突）

跨团队聚合 vkey 方案下，model 前缀 ``<team-slug>/<model>`` 会与
``<vendor>/<model>``（如 ``openai/gpt-4o``）命名重叠。
禁止创建/重命名为已知 LiteLLM provider 名的 team slug 消除歧义。
"""

from __future__ import annotations

RESERVED_TEAM_SLUGS: frozenset[str] = frozenset({
    # Major providers
    "openai", "anthropic", "azure", "aws", "bedrock", "vertex_ai", "gemini",
    "google_ai_studio", "mistral", "cohere", "replicate", "huggingface",
    "together_ai", "together", "groq", "perplexity", "ai21", "ai21_studio",
    "deepseek", "openrouter", "cerebras", "sambanova", "fireworks",
    "meta_llama", "llama", "cloudflare", "voyage", "jina_ai",
    # Chinese providers
    "zhipu", "zhipuai", "moonshot", "qwen", "dashscope", "tongyi",
    "minimax", "baichuan", "yi", "lingyi", "doubao", "bytedance",
    "volcengine", "tencent", "hunyuan", "wenxin", "baidu", "iflytek",
    # Others
    "deepinfra", "anyscale", "databricks", "petals", "ollama",
    "ollama_hosted", "vllm", "triton", "text_completion_openai",
    "text_completion_cohere", "aleph_alpha", "nlp_cloud", "xai",
})


def assert_slug_not_reserved(slug: str) -> None:
    """拒绝使用保留字作为 team slug。

    Raises:
        ValueError: slug（小写后）在保留列表中。
    """
    if slug.lower() in RESERVED_TEAM_SLUGS:
        raise ValueError(
            f"Team slug '{slug}' is reserved (matches a known LLM provider name); "
            "choose a different slug to avoid conflicts with model prefix routing"
        )


__all__ = ["RESERVED_TEAM_SLUGS", "assert_slug_not_reserved"]
