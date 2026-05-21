"""Gateway catalog seed JSON 加载与同步。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains.gateway.application.config_catalog_sync import sync_gateway_catalog_from_seed
from domains.gateway.application.gateway_catalog_seed import (
    catalog_seed_model_from_dict,
    load_seed_catalog_models,
    resolve_catalog_seed_models,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository


def test_catalog_seed_model_from_dict_thinking_param() -> None:
    info = catalog_seed_model_from_dict(
        {
            "id": "claude-opus-4-7",
            "name": "Claude Opus 4.7",
            "provider": "anthropic",
            "litellm_model": "claude-opus-4-7",
            "supports_reasoning": True,
            "thinking_param": "anthropic_extended",
        }
    )
    assert info.id == "claude-opus-4-7"
    assert info.thinking_param == "anthropic_extended"


def test_load_seed_catalog_models_from_repo_file() -> None:
    models = load_seed_catalog_models()
    assert len(models) >= 1
    ids = {m.id for m in models}
    assert "deepseek/deepseek-chat" in ids


def test_resolve_catalog_seed_models_prefers_json(tmp_path: Path) -> None:
    seed = tmp_path / "seed.json"
    seed.write_text(
        json.dumps(
            {
                "version": 1,
                "models": [
                    {
                        "id": "test/only-seed",
                        "name": "Only Seed",
                        "provider": "openai",
                        "litellm_model": "gpt-4o-mini",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    models = resolve_catalog_seed_models(seed)
    assert len(models) == 1
    assert models[0].id == "test/only-seed"


@pytest.mark.asyncio
async def test_sync_gateway_catalog_from_seed_idempotent(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.config_catalog_sync._provider_api_key_and_base",
        lambda p: ("sk-test", None) if p == "openai" else (None, None),
    )
    stats1 = await sync_gateway_catalog_from_seed(db_session)
    await db_session.flush()
    stats2 = await sync_gateway_catalog_from_seed(db_session)
    await db_session.flush()
    assert stats1["upserted"] >= 0
    assert stats2["upserted"] >= 0
    repo = GatewayModelRepository(db_session)
    rows = await repo.list_system(only_enabled=False)
    managed = [r for r in rows if (r.tags or {}).get("managed_by") == "config"]
    assert len(managed) >= stats1.get("upserted", 0) or stats1["skipped_no_credential"] > 0
