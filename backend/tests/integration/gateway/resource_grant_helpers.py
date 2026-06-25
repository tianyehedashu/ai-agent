"""个人资源 grant 集成测试共享 helpers。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from httpx import AsyncClient


async def setup_personal_byok_model(
    dev_client: AsyncClient,
    headers: dict[str, str],
    *,
    model_name: str | None = None,
    provider: str = "openai",
    real_model: str = "gpt-4o-mini",
) -> tuple[str, str, str]:
    """创建个人 BYOK 凭据 + 注册模型，返回 (credential_id, model_id, model_name)。"""
    name = model_name or f"granted-{uuid.uuid4().hex[:8]}"
    r_cred = await dev_client.post(
        "/api/v1/gateway/my-credentials",
        headers=headers,
        json={
            "provider": provider,
            "name": f"cred-{uuid.uuid4().hex[:6]}",
            "api_key": "sk-resource-grant-int-test-key-123456789",
        },
    )
    assert r_cred.status_code == 201, r_cred.text
    cred_id = r_cred.json()["id"]

    r_model = await dev_client.post(
        "/api/v1/gateway/my-models",
        headers=headers,
        json={
            "display_name": name,
            "provider": provider,
            "model_id": real_model,
            "credential_id": cred_id,
            "model_types": ["text"],
        },
    )
    assert r_model.status_code == 201, r_model.text
    body = r_model.json()
    row = body[0] if isinstance(body, list) else body
    model_id = row["id"]
    return cred_id, model_id, row["name"]


async def grant_model_to_teams(
    dev_client: AsyncClient,
    headers: dict[str, str],
    *,
    model_id: str,
    target_team_ids: list[uuid.UUID],
) -> list[dict]:
    r = await dev_client.post(
        "/api/v1/gateway/resource-grants",
        headers=headers,
        json={
            "subject_kind": "model",
            "subject_id": model_id,
            "target_team_ids": [str(tid) for tid in target_team_ids],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def grant_credential_to_teams(
    dev_client: AsyncClient,
    headers: dict[str, str],
    *,
    credential_id: str,
    target_team_ids: list[uuid.UUID],
) -> list[dict]:
    r = await dev_client.post(
        "/api/v1/gateway/resource-grants",
        headers=headers,
        json={
            "subject_kind": "credential",
            "subject_id": credential_id,
            "target_team_ids": [str(tid) for tid in target_team_ids],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()
