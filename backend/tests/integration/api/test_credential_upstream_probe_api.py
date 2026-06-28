"""凭据上游探测与批量导入 — HTTP 集成测试（ASGI + JWT，上游 httpx 可 mock）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.application.management.ports import RawUpstreamListResult
from domains.gateway.infrastructure.upstream.openai_compatible_model_list_adapter import (
    OpenAICompatibleModelListAdapter,
)
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService


def _model_list_items(payload: dict | list) -> list:
    if isinstance(payload, dict) and "items" in payload:
        return payload["items"]
    if isinstance(payload, list):
        return payload
    raise TypeError(f"unexpected models list payload: {type(payload)!r}")


def _mock_models_list() -> RawUpstreamListResult:
    return RawUpstreamListResult(
        ok=True,
        http_status=200,
        items=(
            ("e2e-model-a", "openai"),
            ("e2e-model-b", "openai"),
        ),
        error_message=None,
    )


@pytest.mark.integration
class TestCredentialUpstreamProbeApi:
    @pytest.mark.asyncio
    async def test_my_probe_anthropic_returns_200_unsupported(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        r1 = await client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "anthropic",
                "name": f"probe-anth-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-ant-placeholder",
                "api_base": None,
            },
        )
        assert r1.status_code == 201, r1.text
        cid = r1.json()["id"]

        pr = await client.post(
            f"/api/v1/gateway/my-credentials/{cid}/probe",
            headers=auth_headers,
            json={},
        )
        assert pr.status_code == 200, pr.text
        body = pr.json()
        assert body["support"] == "unsupported"
        assert body["upstream"] == "none"
        assert body["items"] == []

        await client.delete(f"/api/v1/gateway/my-credentials/{cid}", headers=auth_headers)

    @pytest.mark.asyncio
    async def test_my_probe_and_batch_import_with_mocked_upstream(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        r1 = await client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"probe-openai-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-test-mock-openai",
                "api_base": None,
            },
        )
        assert r1.status_code == 201, r1.text
        cid = r1.json()["id"]

        with patch.object(
            OpenAICompatibleModelListAdapter,
            "fetch_models",
            new=AsyncMock(return_value=_mock_models_list()),
        ):
            pr = await client.post(
                f"/api/v1/gateway/my-credentials/{cid}/probe",
                headers=auth_headers,
                json={},
            )
        assert pr.status_code == 200, pr.text
        probe = pr.json()
        assert probe["support"] == "full"
        assert len(probe["items"]) == 2
        ids = {x["id"] for x in probe["items"]}
        assert ids == {"e2e-model-a", "e2e-model-b"}
        for item in probe["items"]:
            assert "inferred_model_types" in item
            assert isinstance(item["inferred_model_types"], list)
            assert len(item["inferred_model_types"]) >= 1

        with patch.object(
            OpenAICompatibleModelListAdapter,
            "fetch_models",
            new=AsyncMock(return_value=_mock_models_list()),
        ):
            br = await client.post(
                f"/api/v1/gateway/my-credentials/{cid}/batch-import-models",
                headers=auth_headers,
                json={
                    "provider": "openai",
                    "upstream_model_ids": ["e2e-model-a"],
                    "model_types": ["text"],
                    "display_name_prefix": "E2E",
                    "enabled": True,
                },
            )
        assert br.status_code == 201, br.text
        batch = br.json()
        assert batch["credential_id"] == cid
        assert len(batch["created"]) == 1
        assert batch["created"][0]["upstream_model_id"] == "e2e-model-a"
        assert len(batch["created"][0]["gateway_model_ids"]) >= 1
        assert batch["failed"] == []

        listed = await client.get("/api/v1/gateway/my-models", headers=auth_headers)
        assert listed.status_code == 200
        names = {m.get("display_name") for m in _model_list_items(listed.json())}
        assert any(n and "e2e-model-a" in n for n in names)

        for mid in batch["created"][0]["gateway_model_ids"]:
            await client.delete(f"/api/v1/gateway/my-models/{mid}", headers=auth_headers)
        await client.delete(f"/api/v1/gateway/my-credentials/{cid}", headers=auth_headers)

    @pytest.mark.asyncio
    async def test_probe_inferred_model_types_unions_litellm_vision(
        self, client: AsyncClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from domains.gateway.domain.litellm.litellm_capability_mapping import LitellmModelInfoHints
        from domains.gateway.infrastructure.litellm.litellm_capability_hint_adapter import (
            LitellmCapabilityHintAdapter,
        )

        r1 = await client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "volcengine",
                "name": f"probe-volc-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-volc-mock",
                "api_base": None,
            },
        )
        assert r1.status_code == 201, r1.text
        cid = r1.json()["id"]

        def _volc_vision_hints(_self, *, provider: str, real_model: str) -> LitellmModelInfoHints:
            _ = provider, real_model
            return LitellmModelInfoHints(supports_vision=True)

        monkeypatch.setattr(LitellmCapabilityHintAdapter, "get_model_hints", _volc_vision_hints)

        volc_items = RawUpstreamListResult(
            ok=True,
            http_status=200,
            items=(("doubao-seed-2-0-lite-260215", "volcengine"),),
            error_message=None,
        )

        with patch.object(
            OpenAICompatibleModelListAdapter,
            "fetch_models",
            new=AsyncMock(return_value=volc_items),
        ):
            pr = await client.post(
                f"/api/v1/gateway/my-credentials/{cid}/probe",
                headers=auth_headers,
                json={},
            )
        assert pr.status_code == 200, pr.text
        probe = pr.json()
        assert probe["support"] == "full"
        assert len(probe["items"]) == 1
        inferred = probe["items"][0]["inferred_model_types"]
        assert "text" in inferred
        assert "image" in inferred

        await client.delete(f"/api/v1/gateway/my-credentials/{cid}", headers=auth_headers)

    @pytest.mark.asyncio
    async def test_probe_kimi_k26_infers_vision_via_semantic_provider(
        self, client: AsyncClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typing import Any

        import litellm

        def _selective_model_info(*, model: str) -> dict[str, Any]:
            if model == "moonshot/kimi-k2.6":
                return {"supports_vision": True, "mode": "chat"}
            raise ValueError(f"unmapped: {model}")

        monkeypatch.setattr(litellm, "get_model_info", _selective_model_info)

        r1 = await client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "volcengine",
                "name": f"probe-kimi-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-volc-mock",
                "api_base": None,
            },
        )
        assert r1.status_code == 201, r1.text
        cid = r1.json()["id"]

        volc_items = RawUpstreamListResult(
            ok=True,
            http_status=200,
            items=(("kimi-k2.6", "volcengine"),),
            error_message=None,
        )

        with patch.object(
            OpenAICompatibleModelListAdapter,
            "fetch_models",
            new=AsyncMock(return_value=volc_items),
        ):
            pr = await client.post(
                f"/api/v1/gateway/my-credentials/{cid}/probe",
                headers=auth_headers,
                json={},
            )
        assert pr.status_code == 200, pr.text
        probe = pr.json()
        assert probe["support"] == "full"
        assert len(probe["items"]) == 1
        inferred = probe["items"][0]["inferred_model_types"]
        assert "text" in inferred
        assert "image" in inferred

        await client.delete(f"/api/v1/gateway/my-credentials/{cid}", headers=auth_headers)

    @pytest.mark.asyncio
    async def test_my_batch_import_with_items_per_model_types(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        r1 = await client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"probe-items-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-test-mock-openai-items",
                "api_base": None,
            },
        )
        assert r1.status_code == 201, r1.text
        cid = r1.json()["id"]

        with patch.object(
            OpenAICompatibleModelListAdapter,
            "fetch_models",
            new=AsyncMock(return_value=_mock_models_list()),
        ):
            br = await client.post(
                f"/api/v1/gateway/my-credentials/{cid}/batch-import-models",
                headers=auth_headers,
                json={
                    "provider": "openai",
                    "items": [
                        {
                            "upstream_model_id": "e2e-model-a",
                            "model_types": ["text"],
                        },
                        {
                            "upstream_model_id": "e2e-model-b",
                            "model_types": ["text"],
                        },
                    ],
                    "display_name_prefix": "E2E-Items",
                    "enabled": True,
                },
            )
        assert br.status_code == 201, br.text
        batch = br.json()
        assert batch["credential_id"] == cid
        assert len(batch["created"]) == 2
        created_ids = {c["upstream_model_id"] for c in batch["created"]}
        assert created_ids == {"e2e-model-a", "e2e-model-b"}
        assert batch["failed"] == []

        for row in batch["created"]:
            for mid in row["gateway_model_ids"]:
                await client.delete(f"/api/v1/gateway/my-models/{mid}", headers=auth_headers)
        await client.delete(f"/api/v1/gateway/my-credentials/{cid}", headers=auth_headers)

    @pytest.mark.asyncio
    async def test_my_probe_unknown_credential_404(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        bad_id = uuid.uuid4()
        pr = await client.post(
            f"/api/v1/gateway/my-credentials/{bad_id}/probe",
            headers=auth_headers,
            json={},
        )
        assert pr.status_code == 404

    @pytest.mark.asyncio
    async def test_team_probe_and_batch_with_mocked_upstream(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        name = f"team-probe-{uuid.uuid4().hex[:8]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": name,
                "api_key": "sk-team-mock-openai-key",
                "api_base": None,
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]

        with patch.object(
            OpenAICompatibleModelListAdapter,
            "fetch_models",
            new=AsyncMock(return_value=_mock_models_list()),
        ):
            pr = await dev_client.post(
                f"/api/v1/gateway/teams/{team.id}/credentials/{cid}/probe",
                headers=headers,
                json={},
            )
        assert pr.status_code == 200, pr.text
        assert pr.json()["support"] == "full"

        alias = f"e2e-alias-{uuid.uuid4().hex[:6]}"
        with patch.object(
            OpenAICompatibleModelListAdapter,
            "fetch_models",
            new=AsyncMock(return_value=_mock_models_list()),
        ):
            br = await dev_client.post(
                f"/api/v1/gateway/teams/{team.id}/credentials/{cid}/batch-import-models",
                headers=headers,
                json={
                    "provider": "openai",
                    "capability": "chat",
                    "weight": 1,
                    "enabled": True,
                    "items": [{"upstream_model_id": "e2e-model-b", "name": alias}],
                },
            )
        assert br.status_code == 201, br.text
        batch = br.json()
        assert len(batch["created"]) == 1
        assert batch["failed"] == []
        gid = batch["created"][0]["gateway_model_id"]

        await dev_client.delete(f"/api/v1/gateway/teams/{team.id}/models/{gid}", headers=headers)
        await dev_client.delete(
            f"/api/v1/gateway/teams/{team.id}/credentials/{cid}", headers=headers
        )

    @pytest.mark.asyncio
    async def test_system_credential_batch_import_lists_as_system_registry(
        self,
        dev_client: AsyncClient,
        admin_user: User,
        admin_headers: dict[str, str],
        db_session,
    ) -> None:
        """系统凭据批量导入应写入 system_gateway_models，列表 registry_scope=system 可见。"""
        team = await TeamService(db_session).ensure_personal_team(admin_user.id)
        await db_session.commit()
        headers = admin_headers
        cred_name = f"sys-batch-{uuid.uuid4().hex[:8]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": cred_name,
                "api_key": "sk-system-batch-integration-test-key",
                "api_base": None,
                "scope": "system",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        alias = f"sys-alias-{uuid.uuid4().hex[:6]}"

        with patch.object(
            OpenAICompatibleModelListAdapter,
            "fetch_models",
            new=AsyncMock(return_value=_mock_models_list()),
        ):
            br = await dev_client.post(
                f"/api/v1/gateway/teams/{team.id}/credentials/{cid}/batch-import-models",
                headers=headers,
                json={
                    "provider": "openai",
                    "capability": "chat",
                    "weight": 1,
                    "enabled": True,
                    "items": [{"upstream_model_id": "e2e-model-b", "name": alias}],
                },
            )
        assert br.status_code == 201, br.text
        batch = br.json()
        assert len(batch["created"]) == 1
        gid = batch["created"][0]["gateway_model_id"]

        r_list = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            params={"registry_scope": "system"},
        )
        assert r_list.status_code == 200, r_list.text
        by_id = {item["id"]: item for item in _model_list_items(r_list.json())}
        assert gid in by_id
        assert by_id[gid]["registry_kind"] == "system"
        assert by_id[gid]["name"] == alias

        r_team = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            params={"registry_scope": "team"},
        )
        assert r_team.status_code == 200, r_team.text
        team_ids = {item["id"] for item in _model_list_items(r_team.json())}
        assert gid not in team_ids

        await dev_client.delete(f"/api/v1/gateway/teams/{team.id}/models/{gid}", headers=headers)
        await dev_client.delete(
            f"/api/v1/gateway/teams/{team.id}/credentials/{cid}",
            headers=headers,
        )
