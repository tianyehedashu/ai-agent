"""APIEmbedding 经 Gateway 桥接单测（T10 单元层）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domains.agent.infrastructure.llm.embeddings import APIEmbedding, LocalEmbedding


@pytest.mark.asyncio
async def test_api_embedding_calls_gateway_proxy() -> None:
    proxy = MagicMock()
    proxy.embedding = AsyncMock(return_value=[[0.1, 0.2]])
    emb = APIEmbedding(model="text-embedding-3-small", gateway_proxy=proxy)
    uid = __import__("uuid").uuid4()
    with (
        patch(
            "domains.agent.infrastructure.llm.embeddings.resolve_internal_gateway_user_id",
            return_value=uid,
        ),
        patch(
            "domains.agent.infrastructure.llm.embeddings.resolve_gateway_bridge_attribution",
            return_value=MagicMock(actor_user_id=uid, billing_team_id=uid),
        ),
    ):
        vec = await emb.embed("hello")
    assert vec == [0.1, 0.2]
    proxy.embedding.assert_awaited_once()
    call_kw = proxy.embedding.await_args.kwargs
    assert call_kw["model"] == "text-embedding-3-small"
    assert "api_key" not in call_kw


def test_local_embedding_does_not_require_gateway() -> None:
    """FastEmbed 本地路径不依赖 Gateway（刻意设计）。"""
    provider = LocalEmbedding(model_name="BAAI/bge-small-en-v1.5")
    assert provider.model_name == "BAAI/bge-small-en-v1.5"
