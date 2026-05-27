"""
Gateway 管理面 /api/v1/gateway/* 集成测试（dev_client + JWT）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import uuid

from httpx import AsyncClient
import pytest

from bootstrap.config import settings
from domains.gateway.domain.types import CONFIG_MANAGED_BY, GATEWAY_MODEL_MANAGED_BY_TAG
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import VirtualKeyRepository
from domains.identity.application import UserUseCase
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.api.paths import openai_compat_base
from libs.crypto import derive_encryption_key, encrypt_value


def _model_list_items(payload: dict | list) -> list:
    if isinstance(payload, dict) and "items" in payload:
        return payload["items"]
    if isinstance(payload, list):
        return payload
    raise TypeError(f"unexpected models list payload: {type(payload)!r}")


@pytest.mark.integration
class TestGatewayManagementApi:
    @pytest.mark.asyncio
    async def test_list_teams_with_personal_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()

        r = await dev_client.get("/api/v1/gateway/teams", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        personal = next((t for t in data if t.get("kind") == "personal"), None)
        assert personal is not None
        assert personal.get("team_role") == "owner"

    @pytest.mark.asyncio
    async def test_list_teams_membership_only_skips_platform_admin_global_list(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        """membership_only=true 时平台 admin 也仅返回 membership，不含全站 personal team。"""
        r_create = await dev_client.post(
            "/api/v1/gateway/teams",
            headers=auth_headers,
            json={"name": f"MemberOnly-{uuid.uuid4().hex[:8]}"},
        )
        assert r_create.status_code == 201, r_create.text

        r_all = await dev_client.get("/api/v1/gateway/teams", headers=admin_headers)
        r_member = await dev_client.get(
            "/api/v1/gateway/teams",
            headers=admin_headers,
            params={"membership_only": "true"},
        )
        assert r_all.status_code == 200, r_all.text
        assert r_member.status_code == 200, r_member.text
        assert len(r_member.json()) < len(r_all.json())

    @pytest.mark.asyncio
    async def test_list_teams_platform_admin_excludes_anonymous_personal_by_default(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        db_session,
    ) -> None:
        """默认全站列表不含 anonymous personal team；include_anonymous_personal=true 可恢复。"""
        anon = User(
            email=f"anon_{uuid.uuid4()}@anonymous.local",
            hashed_password="x",
            name="Anon",
            role="anonymous",
        )
        db_session.add(anon)
        await db_session.commit()
        await db_session.refresh(anon)
        anon_personal = await TeamService(db_session).ensure_personal_team(anon.id)
        await db_session.commit()

        r_default = await dev_client.get("/api/v1/gateway/teams", headers=admin_headers)
        r_include = await dev_client.get(
            "/api/v1/gateway/teams",
            headers=admin_headers,
            params={"include_anonymous_personal": "true"},
        )
        assert r_default.status_code == 200, r_default.text
        assert r_include.status_code == 200, r_include.text
        default_ids = {item["id"] for item in r_default.json()}
        include_ids = {item["id"] for item in r_include.json()}
        assert str(anon_personal.id) not in default_ids
        assert str(anon_personal.id) in include_ids
        assert len(include_ids) > len(default_ids)

    @pytest.mark.asyncio
    async def test_list_teams_platform_admin_includes_non_membership_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        """平台 admin 可见全站活跃团队；非成员团队 team_role 合成为 admin。"""
        r_create = await dev_client.post(
            "/api/v1/gateway/teams",
            headers=auth_headers,
            json={"name": f"Outsider-{uuid.uuid4().hex[:8]}"},
        )
        assert r_create.status_code == 201, r_create.text
        outsider_team_id = r_create.json()["id"]

        r = await dev_client.get("/api/v1/gateway/teams", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        by_id = {item["id"]: item for item in data}
        assert outsider_team_id in by_id
        assert by_id[outsider_team_id]["team_role"] == "admin"

    @pytest.mark.asyncio
    async def test_add_member_to_personal_team_rejected(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        personal = await TeamService(db_session).ensure_personal_team(test_user.id)
        invitee = User(
            email=f"invitee_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Invitee User",
        )
        db_session.add(invitee)
        await db_session.commit()
        await db_session.refresh(invitee)

        r = await dev_client.post(
            f"/api/v1/gateway/teams/{personal.id}/members",
            headers=auth_headers,
            json={"user_id": str(invitee.id), "role": "member"},
        )
        assert r.status_code == 400, r.text
        assert "Personal teams cannot have members other than the owner" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_lookup_member_by_email_as_admin(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        invitee = User(
            email=f"lookup_target_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Lookup Target",
        )
        db_session.add(invitee)
        await db_session.commit()
        await db_session.refresh(invitee)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Lookup Team", owner_user_id=test_user.id)
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/members/lookup",
            headers=auth_headers,
            params={"email": invitee.email},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == str(invitee.id)
        assert data["email"] == invitee.email
        assert data["name"] == invitee.name
        assert "role" not in data

    @pytest.mark.asyncio
    async def test_lookup_member_by_email_forbidden_for_member(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        member = User(
            email=f"lookup_member_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Lookup Member",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Lookup Forbidden Team", owner_user_id=test_user.id)
        await ts.add_member(shared.id, member.id, "member")
        await db_session.commit()

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {
            "Authorization": f"Bearer {member_token.access_token}",
            "X-Team-Id": str(shared.id),
        }

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/members/lookup",
            headers=member_headers,
            params={"email": test_user.email},
        )
        assert r.status_code == 403, r.text

    @pytest.mark.asyncio
    async def test_lookup_member_by_email_not_found(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        ts = TeamService(db_session)
        shared = await ts.create_team(name="Lookup Not Found Team", owner_user_id=test_user.id)
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/members/lookup",
            headers=auth_headers,
            params={"email": f"no_such_{uuid.uuid4()}@example.com"},
        )
        assert r.status_code == 404, r.text

    @pytest.mark.asyncio
    async def test_get_log_detail(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        log_id = uuid.uuid4()
        cred_id = uuid.uuid4()
        now = datetime.now(UTC)
        row = GatewayRequestLog(
            id=log_id,
            created_at=now,
            tenant_id=team.id,
            user_id=test_user.id,
            vkey_id=None,
            credential_id=cred_id,
            credential_name_snapshot="team-openai",
            capability="chat",
            route_name=None,
            real_model="gpt-4",
            provider="openai",
            status="success",
            input_tokens=10,
            output_tokens=5,
            cached_tokens=0,
            cost_usd=Decimal("0.001"),
            latency_ms=100,
            ttfb_ms=42,
            cache_hit=False,
            fallback_chain=[],
            request_id="req-test",
            prompt_hash="phash",
            prompt_redacted={"messages_preview": [{"role": "user", "content": "hi"}]},
            response_summary={"text": "hello"},
            metadata_extra={"foo": "bar"},
        )
        db_session.add(row)
        await db_session.commit()

        headers = auth_headers
        r = await dev_client.get(f"/api/v1/gateway/teams/{team.id}/logs/{log_id}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == str(log_id)
        assert body["team_id"] == str(team.id)
        assert body["credential_id"] == str(cred_id)
        assert body["credential_name_snapshot"] == "team-openai"
        assert body["ttfb_ms"] == 42
        assert body["prompt_hash"] == "phash"
        assert body["prompt_redacted"]["messages_preview"][0]["role"] == "user"
        assert body["response_summary"]["text"] == "hello"
        assert body["metadata_extra"] == {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_user_aggregation_uses_current_user_not_selected_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        personal = await TeamService(db_session).ensure_personal_team(test_user.id)
        shared = await TeamService(db_session).create_team(
            name="Shared Stats Team",
            owner_user_id=test_user.id,
        )
        now = datetime.now(UTC)
        personal_log_id = uuid.uuid4()
        shared_log_id = uuid.uuid4()
        other_log_id = uuid.uuid4()
        db_session.add_all(
            [
                GatewayRequestLog(
                    id=personal_log_id,
                    created_at=now,
                    tenant_id=personal.id,
                    user_id=test_user.id,
                    vkey_id=None,
                    capability="chat",
                    route_name=None,
                    real_model="gpt-4",
                    provider="openai",
                    status="success",
                    input_tokens=10,
                    output_tokens=5,
                    cached_tokens=0,
                    cost_usd=Decimal("0.001"),
                    latency_ms=100,
                    cache_hit=False,
                    fallback_chain=[],
                    request_id="req-personal",
                ),
                GatewayRequestLog(
                    id=shared_log_id,
                    created_at=now,
                    tenant_id=shared.id,
                    user_id=test_user.id,
                    vkey_id=None,
                    capability="chat",
                    route_name=None,
                    real_model="gpt-4",
                    provider="openai",
                    status="success",
                    input_tokens=3,
                    output_tokens=2,
                    cached_tokens=0,
                    cost_usd=Decimal("0.001"),
                    latency_ms=120,
                    cache_hit=False,
                    fallback_chain=[],
                    request_id="req-shared",
                ),
                GatewayRequestLog(
                    id=other_log_id,
                    created_at=now,
                    tenant_id=shared.id,
                    user_id=uuid.uuid4(),
                    vkey_id=None,
                    capability="chat",
                    route_name=None,
                    real_model="gpt-4",
                    provider="openai",
                    status="success",
                    input_tokens=100,
                    output_tokens=50,
                    cached_tokens=0,
                    cost_usd=Decimal("1"),
                    latency_ms=150,
                    cache_hit=False,
                    fallback_chain=[],
                    request_id="req-other",
                ),
            ]
        )
        await db_session.commit()

        headers = auth_headers
        logs = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/logs?usage_aggregation=user&page_size=10",
            headers=headers,
        )
        assert logs.status_code == 200, logs.text
        ids = {item["id"] for item in logs.json()["items"]}
        assert str(personal_log_id) in ids
        assert str(shared_log_id) in ids
        assert str(other_log_id) not in ids

        detail = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/logs/{personal_log_id}?usage_aggregation=user",
            headers=headers,
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["id"] == str(personal_log_id)

        summary = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/dashboard/summary?usage_aggregation=user&days=1",
            headers=headers,
        )
        assert summary.status_code == 200, summary.text
        body = summary.json()
        assert body["total_requests"] == 2
        assert body["total_input_tokens"] == 13
        assert body["total_output_tokens"] == 7

    @pytest.mark.asyncio
    async def test_workspace_logs_member_sql_filter_own_vkeys_and_own_platform_inbound(
        self,
        dev_client: AsyncClient,
        db_session,
        test_user: User,
    ) -> None:
        """团队成员视角（usage_aggregation=workspace）：列表 total/分页与 SQL EXISTS 一致；详情权限与单条查询一致。"""
        owner = test_user
        member = User(
            email=f"member_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Member User",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Shared Logs Team", owner_user_id=owner.id)
        await ts.add_member(shared.id, member.id, "member")

        vkeys = VirtualKeyRepository(db_session)
        owner_key = await vkeys.create(
            tenant_id=shared.id,
            created_by_user_id=owner.id,
            name="owner-vk",
            description=None,
            key_id_str=uuid.uuid4().hex[:16],
            key_hash=f"hash-owner-{uuid.uuid4()}",
            encrypted_key="k" * 64,
            allowed_models=[],
            allowed_capabilities=[],
            rpm_limit=None,
            tpm_limit=None,
            store_full_messages=False,
            guardrail_enabled=True,
            is_system=False,
        )
        member_key = await vkeys.create(
            tenant_id=shared.id,
            created_by_user_id=member.id,
            name="member-vk",
            description=None,
            key_id_str=uuid.uuid4().hex[:16],
            key_hash=f"hash-member-{uuid.uuid4()}",
            encrypted_key="k" * 64,
            allowed_models=[],
            allowed_capabilities=[],
            rpm_limit=None,
            tpm_limit=None,
            store_full_messages=False,
            guardrail_enabled=True,
            is_system=False,
        )
        await db_session.commit()

        now = datetime.now(UTC)

        def _row(
            log_id: uuid.UUID,
            *,
            vkey_id: uuid.UUID | None,
            user_id: uuid.UUID,
            request_id: str,
        ) -> GatewayRequestLog:
            return GatewayRequestLog(
                id=log_id,
                created_at=now,
                tenant_id=shared.id,
                user_id=user_id,
                vkey_id=vkey_id,
                capability="chat",
                route_name=None,
                real_model="gpt-4",
                provider="openai",
                status="success",
                input_tokens=1,
                output_tokens=1,
                cached_tokens=0,
                cost_usd=Decimal("0.001"),
                latency_ms=10,
                cache_hit=False,
                fallback_chain=[],
                request_id=request_id,
            )

        log_member_vkey = uuid.uuid4()
        log_owner_vkey = uuid.uuid4()
        log_member_platform = uuid.uuid4()
        log_owner_platform = uuid.uuid4()
        db_session.add_all(
            [
                _row(log_member_vkey, vkey_id=member_key.id, user_id=owner.id, request_id="m-vk"),
                _row(log_owner_vkey, vkey_id=owner_key.id, user_id=member.id, request_id="o-vk"),
                _row(log_member_platform, vkey_id=None, user_id=member.id, request_id="m-plat"),
                _row(log_owner_platform, vkey_id=None, user_id=owner.id, request_id="o-plat"),
            ]
        )
        await db_session.commit()

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {"Authorization": f"Bearer {member_token.access_token}"}
        team_headers = member_headers

        logs = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/logs",
            params={"usage_aggregation": "workspace", "page_size": 50, "page": 1},
            headers=team_headers,
        )
        assert logs.status_code == 200, logs.text
        body = logs.json()
        assert body["total"] == 2
        ids = {item["id"] for item in body["items"]}
        assert ids == {str(log_member_vkey), str(log_member_platform)}

        ok = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/logs/{log_member_vkey}",
            params={"usage_aggregation": "workspace"},
            headers=team_headers,
        )
        assert ok.status_code == 200, ok.text

        denied = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/logs/{log_owner_vkey}",
            params={"usage_aggregation": "workspace"},
            headers=team_headers,
        )
        assert denied.status_code == 403, denied.text

        filtered_other_vkey = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/logs",
            params={
                "usage_aggregation": "workspace",
                "vkey_id": str(owner_key.id),
                "page_size": 50,
                "page": 1,
            },
            headers=team_headers,
        )
        assert filtered_other_vkey.status_code == 200, filtered_other_vkey.text
        other_body = filtered_other_vkey.json()
        assert other_body["total"] == 0
        assert other_body["items"] == []

        filtered_own_vkey = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/logs",
            params={
                "usage_aggregation": "workspace",
                "vkey_id": str(member_key.id),
                "page_size": 50,
                "page": 1,
            },
            headers=team_headers,
        )
        assert filtered_own_vkey.status_code == 200, filtered_own_vkey.text
        own_body = filtered_own_vkey.json()
        assert own_body["total"] == 1
        assert {item["id"] for item in own_body["items"]} == {str(log_member_vkey)}

    @pytest.mark.asyncio
    async def test_list_model_presets_filter_by_provider(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        r_all = await dev_client.get(f"/api/v1/gateway/teams/{team.id}/models/presets", headers=headers)
        assert r_all.status_code == 200, r_all.text
        all_presets = r_all.json()
        if not all_presets:
            pytest.skip("no catalog presets in environment")
        p0 = str(all_presets[0]["provider"])
        r_f = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models/presets",
            params={"provider": p0},
            headers=headers,
        )
        assert r_f.status_code == 200, r_f.text
        filtered = r_f.json()
        assert all(str(x["provider"]) == p0 for x in filtered)
        assert len(filtered) <= len(all_presets)

    @pytest.mark.asyncio
    async def test_get_managed_credential_and_list_models_by_credential_id(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        name = f"int-test-cred-{uuid.uuid4().hex[:8]}"
        r_create = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": name,
                "api_key": "sk-int-test-key-for-gateway-123456",
                "api_base": None,
                "scope": "team",
            },
        )
        assert r_create.status_code == 201, r_create.text
        cred_body = r_create.json()
        cid = cred_body["id"]
        assert "api_key_masked" in cred_body
        assert "sk-int-test-key-for-gateway-123456" not in cred_body["api_key_masked"]

        r_get = await dev_client.get(f"/api/v1/gateway/teams/{team.id}/credentials/{cid}", headers=headers)
        assert r_get.status_code == 200, r_get.text
        got = r_get.json()
        assert got["id"] == cid
        assert got["name"] == name

        r_reveal = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/credentials/{cid}/reveal",
            headers=headers,
        )
        assert r_reveal.status_code == 200, r_reveal.text
        assert r_reveal.json()["api_key"] == "sk-int-test-key-for-gateway-123456"

        r_models = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            params={"credential_id": cid},
        )
        assert r_models.status_code == 200, r_models.text
        models = _model_list_items(r_models.json())
        assert all(m["credential_id"] == cid for m in models)

    @pytest.mark.asyncio
    async def test_list_models_returns_paginated_envelope(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=auth_headers,
            params={"page": 1, "page_size": 5},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("items", "total", "page", "page_size", "has_next", "has_prev", "connectivity_summary"):
            assert key in body
        assert body["page"] == 1
        assert body["page_size"] == 5
        assert isinstance(body["items"], list)
        summary = body["connectivity_summary"]
        assert summary["total"] == body["total"]
        assert summary["available"] + summary["unavailable"] == summary["total"]

    @pytest.mark.asyncio
    async def test_list_team_models_filters_by_registry_type(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """GET .../models?type= 与注册表 model_types 推导一致（chat+supports_vision 命中 image）。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": f"type-filter-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-type-filter-test-key-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        text_only = f"text-only-{uuid.uuid4().hex[:6]}"
        vision_alias = f"vision-{uuid.uuid4().hex[:6]}"
        for name, tags in (
            (text_only, {"supports_vision": False}),
            (vision_alias, {"supports_vision": True}),
        ):
            r_model = await dev_client.post(
                f"/api/v1/gateway/teams/{team.id}/models",
                headers=headers,
                json={
                    "name": name,
                    "capability": "chat",
                    "real_model": "gpt-4o-mini",
                    "credential_id": cid,
                    "provider": "openai",
                    "tags": tags,
                },
            )
            assert r_model.status_code == 201, r_model.text

        r_image = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            params={"credential_id": cid, "type": "image", "page_size": 50},
        )
        assert r_image.status_code == 200, r_image.text
        image_names = {m["name"] for m in _model_list_items(r_image.json())}
        assert vision_alias in image_names
        assert text_only not in image_names

        r_text = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            params={"credential_id": cid, "type": "text", "page_size": 50},
        )
        assert r_text.status_code == 200, r_text.text
        text_names = {m["name"] for m in _model_list_items(r_text.json())}
        assert text_only in text_names
        assert vision_alias in text_names

    @pytest.mark.asyncio
    async def test_list_system_models_connectivity_summary_matches_total(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        admin_user: User,
        db_session,
    ) -> None:
        """系统注册表分页列表的 connectivity_summary 与 total 一致（SQL 聚合路径）。"""
        team = await TeamService(db_session).ensure_personal_team(admin_user.id)
        await db_session.commit()
        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=admin_headers,
            params={"registry_scope": "system", "page": 1, "page_size": 20},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        summary = body["connectivity_summary"]
        assert summary["total"] == body["total"]
        assert summary["success"] + summary["failed"] + summary["unknown"] == summary["total"]

    @pytest.mark.asyncio
    async def test_list_model_ids_returns_ids_envelope(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models/ids",
            headers=auth_headers,
            params={"page": 1, "page_size": 5},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "ids" in body
        assert "truncated" in body
        assert isinstance(body["ids"], list)
        assert body["truncated"] is False

    @pytest.mark.asyncio
    async def test_list_my_models_returns_paginated_envelope(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        r = await dev_client.get(
            "/api/v1/gateway/my-models",
            headers=auth_headers,
            params={"page": 1, "page_size": 5},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("items", "total", "page", "page_size", "has_next", "has_prev", "connectivity_summary"):
            assert key in body
        assert body["page"] == 1
        assert body["page_size"] == 5
        assert isinstance(body["items"], list)

    @pytest.mark.asyncio
    async def test_delete_managed_credential_cascades_models(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        cred_name = f"del-cascade-{uuid.uuid4().hex[:8]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": cred_name,
                "api_key": "sk-int-del-cascade-key-12345678",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        model_name = f"vm-del-{uuid.uuid4().hex[:6]}"
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            json={
                "name": model_name,
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cid,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text
        model_body = r_model.json()
        mid = model_body["id"]
        assert model_body["tenant_id"] == str(team.id)
        assert model_body["team_id"] == str(team.id)

        r_del = await dev_client.delete(f"/api/v1/gateway/teams/{team.id}/credentials/{cid}", headers=headers)
        assert r_del.status_code == 204, r_del.text

        r_cred_after = await dev_client.get(f"/api/v1/gateway/teams/{team.id}/credentials/{cid}", headers=headers)
        assert r_cred_after.status_code == 404

        r_models_after = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            params={"credential_id": cid},
        )
        assert r_models_after.status_code == 200, r_models_after.text
        assert not any(m["id"] == mid for m in _model_list_items(r_models_after.json()))

    @pytest.mark.asyncio
    async def test_team_create_model_normalizes_dashscope_real_model(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """团队 POST /models：短 id 落库为 LiteLLM 全称；前缀与 provider 不一致时 400。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        cred_name = f"dscope-{uuid.uuid4().hex[:8]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "dashscope",
                "name": cred_name,
                "api_key": "sk-dashscope-int-test-key-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        model_name = f"alias-{uuid.uuid4().hex[:6]}"
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            json={
                "name": model_name,
                "capability": "chat",
                "real_model": "qwen-max",
                "credential_id": cid,
                "provider": "dashscope",
            },
        )
        assert r_model.status_code == 201, r_model.text
        assert r_model.json()["real_model"] == "dashscope/qwen-max"

        r_bad = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            json={
                "name": f"alias-bad-{uuid.uuid4().hex[:6]}",
                "capability": "chat",
                "real_model": "openai/gpt-4",
                "credential_id": cid,
                "provider": "dashscope",
            },
        )
        assert r_bad.status_code == 400, r_bad.text

    @pytest.mark.asyncio
    async def test_team_create_model_rejects_provider_cred_mismatch(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """团队 POST /models：provider 与凭据 provider 不一致时 400。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        r_openai = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": f"oa-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-openai-mismatch-test-123456789",
                "scope": "team",
            },
        )
        assert r_openai.status_code == 201, r_openai.text
        cid = r_openai.json()["id"]
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            json={
                "name": f"mismatch-{uuid.uuid4().hex[:6]}",
                "capability": "chat",
                "real_model": "qwen-max",
                "credential_id": cid,
                "provider": "dashscope",
            },
        )
        assert r_model.status_code == 400, r_model.text
        detail = r_model.json().get("detail", "")
        assert isinstance(detail, str)
        assert "凭据" in detail

    @pytest.mark.asyncio
    async def test_create_managed_credential_azure_with_api_version_extra(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """Azure 凭据可携带 api_version 等 extra 字段；tenant_id 落库正确。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        name = f"azure-{uuid.uuid4().hex[:8]}"
        r = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "azure",
                "name": name,
                "api_key": "az-int-test-key-1234567890",
                "api_base": "https://my-azure.openai.azure.com",
                "extra": {"api_version": "2024-08-01-preview"},
                "scope": "team",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["provider"] == "azure"
        assert body["tenant_id"] == str(team.id)
        assert body["scope"] == "team"
        assert body["api_base"] == "https://my-azure.openai.azure.com"
        assert body["extra"] == {"api_version": "2024-08-01-preview"}

    @pytest.mark.asyncio
    async def test_create_managed_credential_bedrock_with_aws_extras(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """Bedrock 凭据：api_key 装 access_key_id；secret/region/session_token 放 extra。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        name = f"bedrock-{uuid.uuid4().hex[:8]}"
        r = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "bedrock",
                "name": name,
                "api_key": "AKIAFAKEINTEGRATIONACCESSKEY",
                "extra": {
                    "aws_secret_access_key": "secret-int-test-value",
                    "aws_region_name": "us-east-1",
                },
                "scope": "team",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["provider"] == "bedrock"
        assert body["extra"]["aws_region_name"] == "us-east-1"
        assert body["extra"]["aws_secret_access_key"] == "secret-int-test-value"

    @pytest.mark.asyncio
    async def test_create_managed_credential_volcengine_coding_plan_normalizes_api_base(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """Volcengine Coding Plan：无 /v3 的 api_base 入库前补全为 OpenAI-compat 根。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        name = f"ve-cp-{uuid.uuid4().hex[:8]}"
        r = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "volcengine",
                "name": name,
                "api_key": "vk-int-test-key-123456789012",
                "api_base": "https://ark.cn-beijing.volces.com/api/coding",
                "profile_id": "volcengine.coding_plan",
                "scope": "team",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["profile_id"] == "volcengine.coding_plan"
        assert body["api_base"] == "https://ark.cn-beijing.volces.com/api/coding/v3"
        assert body["api_bases"] is not None
        assert body["api_bases"]["openai_compat"] == body["api_base"]
        assert body["effective_api_base_openai"] == (
            "https://ark.cn-beijing.volces.com/api/coding/v3"
        )
        assert body["effective_api_base_anthropic"] == (
            "https://ark.cn-beijing.volces.com/api/coding"
        )

    @pytest.mark.asyncio
    async def test_list_provider_profiles_requires_auth_and_returns_ssot(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        unauth = await dev_client.get("/api/v1/gateway/provider-profiles")
        assert unauth.status_code in (401, 403), unauth.text

        r = await dev_client.get(
            "/api/v1/gateway/provider-profiles",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        profiles = r.json().get("profiles", [])
        assert isinstance(profiles, list)
        ids = {p["id"] for p in profiles}
        assert "volcengine.coding_plan" in ids
        coding = next(p for p in profiles if p["id"] == "volcengine.coding_plan")
        assert coding["api_bases"]["openai_compat"] == (
            "https://ark.cn-beijing.volces.com/api/coding/v3"
        )
        assert coding["api_bases"]["anthropic_native"] == (
            "https://ark.cn-beijing.volces.com/api/coding"
        )

    @pytest.mark.asyncio
    async def test_create_managed_credential_rejects_unknown_provider(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """未在 MANAGED_GATEWAY_CREDENTIAL_PROVIDERS 白名单内的 provider → 400 ValidationError。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        r = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "nonexistent-vendor",
                "name": f"bad-{uuid.uuid4().hex[:6]}",
                "api_key": "irrelevant",
                "scope": "team",
            },
        )
        assert r.status_code == 400, r.text
        assert "nonexistent-vendor" in r.json().get("detail", "")

    @pytest.mark.asyncio
    async def test_my_models_crud(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """个人模型 /my-models 不依赖 X-Team-Id"""
        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"my-model-cred-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-my-models-int-test-key-123456",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_id = r_cred.json()["id"]

        r_create = await dev_client.post(
            "/api/v1/gateway/my-models",
            headers=auth_headers,
            json={
                "display_name": "My GPT",
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "credential_id": cred_id,
                "model_types": ["text"],
            },
        )
        assert r_create.status_code == 201, r_create.text
        created = r_create.json()
        assert len(created) >= 1
        model_id = created[0]["id"]

        r_list = await dev_client.get("/api/v1/gateway/my-models", headers=auth_headers)
        assert r_list.status_code == 200, r_list.text
        assert any(m["id"] == model_id for m in _model_list_items(r_list.json()))

        r_del = await dev_client.delete(
            f"/api/v1/gateway/my-models/{model_id}",
            headers=auth_headers,
        )
        assert r_del.status_code == 204, r_del.text

    @pytest.mark.asyncio
    async def test_my_models_batch_delete(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /my-models/batch-delete 批量删除个人模型。"""
        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"my-batch-cred-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-my-batch-int-test-key-123456",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_id = r_cred.json()["id"]

        model_ids: list[str] = []
        for idx in range(2):
            r_create = await dev_client.post(
                "/api/v1/gateway/my-models",
                headers=auth_headers,
                json={
                    "display_name": f"My Batch {idx}",
                    "provider": "openai",
                    "model_id": f"gpt-4o-mini-{idx}",
                    "credential_id": cred_id,
                    "model_types": ["text"],
                },
            )
            assert r_create.status_code == 201, r_create.text
            model_ids.append(r_create.json()[0]["id"])

        r_batch = await dev_client.post(
            "/api/v1/gateway/my-models/batch-delete",
            headers=auth_headers,
            json={"model_ids": model_ids},
        )
        assert r_batch.status_code == 200, r_batch.text
        body = r_batch.json()
        assert len(body["succeeded"]) == 2
        assert body["failed"] == []

        r_list = await dev_client.get("/api/v1/gateway/my-models", headers=auth_headers)
        assert r_list.status_code == 200, r_list.text
        remaining_ids = {m["id"] for m in _model_list_items(r_list.json())}
        for mid in model_ids:
            assert mid not in remaining_ids

    @pytest.mark.asyncio
    async def test_personal_my_model_listed_on_v1_models(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """个人模型注册别名应出现在 personal team 虚拟 Key 的 GET /v1/models 列表中。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()

        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"v1-models-cred-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-v1-models-int-test-key-123456789",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_id = r_cred.json()["id"]

        r_create = await dev_client.post(
            "/api/v1/gateway/my-models",
            headers=auth_headers,
            json={
                "display_name": "V1 List Test",
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "credential_id": cred_id,
                "model_types": ["text"],
            },
        )
        assert r_create.status_code == 201, r_create.text
        created = r_create.json()
        assert len(created) >= 1
        registration_name = created[0]["name"]
        assert registration_name
        model_id = created[0]["id"]

        mgmt_headers = auth_headers
        ck = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/keys",
            headers=mgmt_headers,
            json={"name": f"itest-personal-model-v1-{uuid.uuid4().hex[:6]}"},
        )
        assert ck.status_code == 201, ck.text
        plain_key = ck.json()["plain_key"]

        r_models = await dev_client.get(
            f"{openai_compat_base()}/models",
            headers={"Authorization": f"Bearer {plain_key}"},
        )
        assert r_models.status_code == 200, r_models.text
        ids = [m["id"] for m in r_models.json().get("data", [])]
        assert registration_name in ids

        r_del = await dev_client.delete(
            f"/api/v1/gateway/my-models/{model_id}",
            headers=auth_headers,
        )
        assert r_del.status_code == 204, r_del.text

    @pytest.mark.asyncio
    async def test_byok_excluded_from_team_registry_scope_but_callable_and_v1(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """BYOK 模型不出现在 registry_scope=team；callable 与 /v1/models 仍可见。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()

        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"team-scope-cred-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-team-scope-int-test-key-123456789",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_id = r_cred.json()["id"]

        r_create = await dev_client.post(
            "/api/v1/gateway/my-models",
            headers=auth_headers,
            json={
                "display_name": "Team Scope Filter",
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "credential_id": cred_id,
                "model_types": ["text"],
            },
        )
        assert r_create.status_code == 201, r_create.text
        created = r_create.json()
        registration_name = created[0]["name"]
        model_id = created[0]["id"]

        r_team = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=auth_headers,
            params={"registry_scope": "team"},
        )
        assert r_team.status_code == 200, r_team.text
        assert registration_name not in {m["name"] for m in _model_list_items(r_team.json())}

        r_callable = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=auth_headers,
            params={"registry_scope": "callable"},
        )
        assert r_callable.status_code == 200, r_callable.text
        assert registration_name in {m["name"] for m in _model_list_items(r_callable.json())}

        ck = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/keys",
            headers=auth_headers,
            json={"name": f"itest-team-scope-{uuid.uuid4().hex[:6]}"},
        )
        assert ck.status_code == 201, ck.text
        plain_key = ck.json()["plain_key"]

        r_v1 = await dev_client.get(
            f"{openai_compat_base()}/models",
            headers={"Authorization": f"Bearer {plain_key}"},
        )
        assert r_v1.status_code == 200, r_v1.text
        assert registration_name in [m["id"] for m in r_v1.json().get("data", [])]

        r_del = await dev_client.delete(
            f"/api/v1/gateway/my-models/{model_id}",
            headers=auth_headers,
        )
        assert r_del.status_code == 204, r_del.text

    @pytest.mark.asyncio
    async def test_provider_and_entitlement_plan_management_apis(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """三组套餐管理 API：ProviderPlan、EntitlementPlan、usage/margin 读入口。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        now = datetime.now(UTC).replace(microsecond=0)
        valid_from = (now - timedelta(minutes=1)).isoformat()
        valid_until = (now + timedelta(days=30)).isoformat()

        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": f"plan-cred-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-plan-api-test-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        credential_id = r_cred.json()["id"]

        r_provider_create = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials/{credential_id}/provider-plans",
            headers=headers,
            json={
                "real_model": "openai/gpt-4o-mini",
                "label": "OpenAI daily pack",
                "valid_from": valid_from,
                "valid_until": valid_until,
                "auto_renew": True,
                "quotas": [
                    {
                        "label": "daily",
                        "window_seconds": 86400,
                        "reset_strategy": "calendar_daily_utc",
                        "limit_requests": 100,
                    }
                ],
            },
        )
        assert r_provider_create.status_code == 201, r_provider_create.text
        provider_plan = r_provider_create.json()
        provider_plan_id = provider_plan["id"]
        assert provider_plan["quotas"][0]["reset_strategy"] == "calendar_daily_utc"

        r_provider_list = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/credentials/{credential_id}/provider-plans",
            headers=headers,
        )
        assert r_provider_list.status_code == 200, r_provider_list.text
        assert any(p["id"] == provider_plan_id for p in r_provider_list.json())

        r_provider_patch = await dev_client.patch(
            f"/api/v1/gateway/teams/{team.id}/credentials/{credential_id}/provider-plans/{provider_plan_id}",
            headers=headers,
            json={
                "label": "OpenAI monthly pack",
                "quotas": [
                    {
                        "label": "monthly",
                        "window_seconds": 31 * 86400,
                        "reset_strategy": "calendar_monthly_utc",
                        "limit_requests": 1000,
                    }
                ],
            },
        )
        assert r_provider_patch.status_code == 200, r_provider_patch.text
        assert r_provider_patch.json()["label"] == "OpenAI monthly pack"
        assert r_provider_patch.json()["quotas"][0]["reset_strategy"] == "calendar_monthly_utc"

        r_provider_usage = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/credentials/{credential_id}/provider-plan-usage?days=7",
            headers=headers,
        )
        assert r_provider_usage.status_code == 200, r_provider_usage.text
        assert isinstance(r_provider_usage.json(), list)

        r_key = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/keys",
            headers=headers,
            json={"name": f"plan-vkey-{uuid.uuid4().hex[:8]}"},
        )
        assert r_key.status_code == 201, r_key.text
        vkey_id = r_key.json()["id"]

        r_ent_create = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/keys/{vkey_id}/entitlements",
            headers=headers,
            json={
                "label": "Customer daily pack",
                "valid_from": valid_from,
                "valid_until": valid_until,
                "included_models": ["gpt-4o-mini"],
                "included_capabilities": ["chat"],
                "quotas": [
                    {
                        "label": "daily",
                        "window_seconds": 86400,
                        "reset_strategy": "calendar_daily_utc",
                        "limit_requests": 10,
                        "unit_price_usd_per_request": "0.01",
                    }
                ],
            },
        )
        assert r_ent_create.status_code == 201, r_ent_create.text
        entitlement = r_ent_create.json()
        entitlement_id = entitlement["id"]
        assert entitlement["scope"] == "vkey"
        assert entitlement["scope_id"] == vkey_id
        assert entitlement["quotas"][0]["reset_strategy"] == "calendar_daily_utc"

        r_ent_list = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/keys/{vkey_id}/entitlements",
            headers=headers,
        )
        assert r_ent_list.status_code == 200, r_ent_list.text
        assert any(p["id"] == entitlement_id for p in r_ent_list.json())

        r_ent_patch = await dev_client.patch(
            f"/api/v1/gateway/teams/{team.id}/entitlements/{entitlement_id}",
            headers=headers,
            json={"label": "Customer monthly pack", "included_models": ["gpt-4o-mini", "gpt-4o"]},
        )
        assert r_ent_patch.status_code == 200, r_ent_patch.text
        assert r_ent_patch.json()["label"] == "Customer monthly pack"
        assert r_ent_patch.json()["included_models"] == ["gpt-4o-mini", "gpt-4o"]

        r_ent_usage = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/entitlements/{entitlement_id}/usage?days=7",
            headers=headers,
        )
        assert r_ent_usage.status_code == 200, r_ent_usage.text
        assert r_ent_usage.json()["plan_id"] == entitlement_id

        r_margin = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/dashboard/margin?days=7&group_by=credential",
            headers=headers,
        )
        assert r_margin.status_code == 403, r_margin.text

    @pytest.mark.asyncio
    async def test_plan_apis_reject_cross_team_access(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """ProviderPlan / EntitlementPlan / api-key-grant entitlements API 跨团队应返回 404。

        IDOR 防护：用 team A 的 credential / vkey id，从 team B 的 personal team
        上下文（不同 user，且非平台管理员）访问应得到 404，且不暴露实体存在性。
        """
        team_a = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers_a = auth_headers
        now = datetime.now(UTC).replace(microsecond=0)
        valid_from = (now - timedelta(minutes=1)).isoformat()
        valid_until = (now + timedelta(days=30)).isoformat()

        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team_a.id}/credentials",
            headers=headers_a,
            json={
                "provider": "openai",
                "name": f"cross-team-cred-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-cross-team-test-12345",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        credential_id = r_cred.json()["id"]

        r_pp = await dev_client.post(
            f"/api/v1/gateway/teams/{team_a.id}/credentials/{credential_id}/provider-plans",
            headers=headers_a,
            json={
                "real_model": "openai/gpt-4o-mini",
                "label": "Owner Plan",
                "valid_from": valid_from,
                "valid_until": valid_until,
                "quotas": [
                    {"label": "daily", "window_seconds": 86400, "limit_requests": 100}
                ],
            },
        )
        assert r_pp.status_code == 201, r_pp.text
        provider_plan_id = r_pp.json()["id"]

        r_key = await dev_client.post(
            f"/api/v1/gateway/teams/{team_a.id}/keys",
            headers=headers_a,
            json={"name": f"cross-team-vkey-{uuid.uuid4().hex[:8]}"},
        )
        assert r_key.status_code == 201, r_key.text
        vkey_id = r_key.json()["id"]

        r_ent = await dev_client.post(
            f"/api/v1/gateway/teams/{team_a.id}/keys/{vkey_id}/entitlements",
            headers=headers_a,
            json={
                "label": "Owner Entitlement",
                "valid_from": valid_from,
                "valid_until": valid_until,
                "quotas": [
                    {"label": "daily", "window_seconds": 86400, "limit_requests": 10}
                ],
            },
        )
        assert r_ent.status_code == 201, r_ent.text
        entitlement_id = r_ent.json()["id"]

        intruder = User(
            email=f"intruder_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Intruder",
        )
        db_session.add(intruder)
        await db_session.commit()
        await db_session.refresh(intruder)
        token_pair = await UserUseCase(db_session).create_token(intruder)
        team_b = await TeamService(db_session).ensure_personal_team(intruder.id)
        await db_session.commit()
        headers_b = {
            "Authorization": f"Bearer {token_pair.access_token}",
            "X-Team-Id": str(team_b.id),
        }

        r1 = await dev_client.get(
            f"/api/v1/gateway/teams/{team_b.id}/credentials/{credential_id}/provider-plans",
            headers=headers_b,
        )
        assert r1.status_code == 404, r1.text

        r2 = await dev_client.patch(
            f"/api/v1/gateway/teams/{team_b.id}/credentials/{credential_id}/provider-plans/{provider_plan_id}",
            headers=headers_b,
            json={"label": "hijacked"},
        )
        assert r2.status_code == 404, r2.text

        r3 = await dev_client.delete(
            f"/api/v1/gateway/teams/{team_b.id}/credentials/{credential_id}/provider-plans/{provider_plan_id}",
            headers=headers_b,
        )
        assert r3.status_code == 404, r3.text

        r4 = await dev_client.get(
            f"/api/v1/gateway/teams/{team_b.id}/keys/{vkey_id}/entitlements",
            headers=headers_b,
        )
        assert r4.status_code == 404, r4.text

        r5 = await dev_client.post(
            f"/api/v1/gateway/teams/{team_b.id}/keys/{vkey_id}/entitlements",
            headers=headers_b,
            json={
                "label": "hijack",
                "valid_from": valid_from,
                "valid_until": valid_until,
                "quotas": [
                    {"label": "daily", "window_seconds": 86400, "limit_requests": 1}
                ],
            },
        )
        assert r5.status_code == 404, r5.text

        r6 = await dev_client.patch(
            f"/api/v1/gateway/teams/{team_b.id}/entitlements/{entitlement_id}",
            headers=headers_b,
            json={"label": "hijacked"},
        )
        assert r6.status_code == 404, r6.text

        r7 = await dev_client.delete(
            f"/api/v1/gateway/teams/{team_b.id}/entitlements/{entitlement_id}",
            headers=headers_b,
        )
        assert r7.status_code == 404, r7.text

        r8 = await dev_client.get(
            f"/api/v1/gateway/teams/{team_b.id}/entitlements/{entitlement_id}/usage?days=7",
            headers=headers_b,
        )
        assert r8.status_code == 404, r8.text

        r9 = await dev_client.get(
            f"/api/v1/gateway/teams/{team_b.id}/api-key-grants/{uuid.uuid4()}/entitlements",
            headers=headers_b,
        )
        assert r9.status_code == 404, r9.text

    @pytest.mark.asyncio
    async def test_reveal_virtual_key_returns_plain(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers

        r_create = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/keys",
            headers=headers,
            json={"name": f"reveal-{uuid.uuid4().hex[:6]}"},
        )
        assert r_create.status_code == 201, r_create.text
        created = r_create.json()
        plain_at_create = created["plain_key"]
        key_id = created["id"]

        r_reveal = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/keys/{key_id}/reveal",
            headers=headers,
        )
        assert r_reveal.status_code == 200, r_reveal.text
        assert r_reveal.json()["plain_key"] == plain_at_create

        r_missing = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/keys/{uuid.uuid4()}/reveal",
            headers=headers,
        )
        assert r_missing.status_code == 404, r_missing.text

        r_revoke = await dev_client.delete(
            f"/api/v1/gateway/teams/{team.id}/keys/{key_id}",
            headers=headers,
        )
        assert r_revoke.status_code == 204, r_revoke.text

        r_reveal_revoked = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/keys/{key_id}/reveal",
            headers=headers,
        )
        assert r_reveal_revoked.status_code == 404, r_reveal_revoked.text

    @pytest.mark.asyncio
    async def test_list_keys_member_sees_only_own(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        owner = test_user
        member = User(
            email=f"member_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Member User",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Shared Keys Team", owner_user_id=owner.id)
        await ts.add_member(shared.id, member.id, "member")
        await db_session.commit()

        owner_headers = auth_headers
        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {
            "Authorization": f"Bearer {member_token.access_token}",
            "X-Team-Id": str(shared.id),
        }

        r_owner_key = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/keys",
            headers=owner_headers,
            json={"name": f"owner-key-{uuid.uuid4().hex[:6]}"},
        )
        assert r_owner_key.status_code == 201, r_owner_key.text
        owner_key_id = r_owner_key.json()["id"]

        r_member_key = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/keys",
            headers=member_headers,
            json={"name": f"member-key-{uuid.uuid4().hex[:6]}"},
        )
        assert r_member_key.status_code == 201, r_member_key.text
        member_key_id = r_member_key.json()["id"]

        r_owner_list = await dev_client.get(f"/api/v1/gateway/teams/{shared.id}/keys", headers=owner_headers)
        assert r_owner_list.status_code == 200, r_owner_list.text
        owner_ids = {item["id"] for item in r_owner_list.json()}
        assert owner_ids == {owner_key_id}

        r_member_list = await dev_client.get(f"/api/v1/gateway/teams/{shared.id}/keys", headers=member_headers)
        assert r_member_list.status_code == 200, r_member_list.text
        member_ids = {item["id"] for item in r_member_list.json()}
        assert member_ids == {member_key_id}

        r_member_reveal_owner = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/keys/{owner_key_id}/reveal",
            headers=member_headers,
        )
        assert r_member_reveal_owner.status_code == 404, r_member_reveal_owner.text

        r_owner_reveal_member = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/keys/{member_key_id}/reveal",
            headers=owner_headers,
        )
        assert r_owner_reveal_member.status_code == 404, r_owner_reveal_member.text

    @pytest.mark.asyncio
    async def test_dashboard_margin_platform_admin_only(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """套餐毛利**仅平台管理员**可见；共享团队 owner/admin、个人工作区均不可见；
        成员调用 summary 时成本字段仍按 admin+ 遮罩（团队 owner 可见）。"""
        owner = test_user
        member = User(
            email=f"member_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Member User",
        )
        platform_admin = User(
            email=f"padmin_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Platform Admin",
            role="admin",
        )
        db_session.add_all([member, platform_admin])
        await db_session.commit()
        await db_session.refresh(member)
        await db_session.refresh(platform_admin)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Dashboard Margin Team", owner_user_id=owner.id)
        await ts.add_member(shared.id, member.id, "member")

        now = datetime.now(UTC)
        db_session.add(
            GatewayRequestLog(
                id=uuid.uuid4(),
                created_at=now,
                tenant_id=shared.id,
                user_id=owner.id,
                vkey_id=None,
                capability="chat",
                route_name=None,
                real_model="gpt-4",
                provider="openai",
                status="success",
                input_tokens=10,
                output_tokens=5,
                cached_tokens=0,
                cost_usd=Decimal("0.01"),
                latency_ms=100,
                cache_hit=False,
                fallback_chain=[],
                request_id=f"margin-test-{uuid.uuid4().hex[:8]}",
            )
        )
        await db_session.commit()

        owner_headers = auth_headers
        uc = UserUseCase(db_session)
        member_token = await uc.create_token(member)
        member_headers = {"Authorization": f"Bearer {member_token.access_token}"}
        admin_token = await uc.create_token(platform_admin)
        admin_headers = {"Authorization": f"Bearer {admin_token.access_token}"}

        r_member_margin = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/dashboard/margin?days=7&group_by=credential",
            headers=member_headers,
        )
        assert r_member_margin.status_code == 403, r_member_margin.text

        r_member_summary = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/dashboard/summary?days=7",
            headers=member_headers,
        )
        assert r_member_summary.status_code == 200, r_member_summary.text
        assert Decimal(str(r_member_summary.json()["total_cost_usd"])) == Decimal("0")

        # 共享团队 owner 也**不可见**套餐毛利（属平台经营数据，仅平台管理员可见）
        r_owner_margin = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/dashboard/margin?days=7&group_by=credential",
            headers=owner_headers,
        )
        assert r_owner_margin.status_code == 403, r_owner_margin.text

        # 但 summary 成本字段仍对团队 owner 可见（团队经营视图）
        r_owner_summary = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/dashboard/summary?days=7",
            headers=owner_headers,
        )
        assert r_owner_summary.status_code == 200, r_owner_summary.text
        assert Decimal(str(r_owner_summary.json()["total_cost_usd"])) == Decimal("0.01")

        # 平台管理员可见（即便不是该团队成员）
        r_admin_margin = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/dashboard/margin?days=7&group_by=credential",
            headers=admin_headers,
        )
        assert r_admin_margin.status_code == 200, r_admin_margin.text
        assert "total_cost_usd" in r_admin_margin.json()

        personal = await ts.ensure_personal_team(owner.id)
        r_personal_margin = await dev_client.get(
            f"/api/v1/gateway/teams/{personal.id}/dashboard/margin?days=7&group_by=credential",
            headers=owner_headers,
        )
        assert r_personal_margin.status_code == 403, r_personal_margin.text

    @pytest.mark.asyncio
    async def test_batch_revoke_virtual_keys(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers

        key_ids: list[str] = []
        for i in range(2):
            r_create = await dev_client.post(
                f"/api/v1/gateway/teams/{team.id}/keys",
                headers=headers,
                json={"name": f"batch-revoke-{i}-{uuid.uuid4().hex[:6]}"},
            )
            assert r_create.status_code == 201, r_create.text
            key_ids.append(r_create.json()["id"])

        r_batch = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/keys/revoke-batch",
            headers=headers,
            json={"key_ids": key_ids},
        )
        assert r_batch.status_code == 200, r_batch.text
        payload = r_batch.json()
        assert payload["revoked"] == key_ids
        assert payload["failed"] == []

        r_list = await dev_client.get(f"/api/v1/gateway/teams/{team.id}/keys", headers=headers)
        assert r_list.status_code == 200, r_list.text
        listed_ids = {item["id"] for item in r_list.json()}
        for key_id in key_ids:
            assert key_id not in listed_ids

        missing_id = str(uuid.uuid4())
        r_partial = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/keys/revoke-batch",
            headers=headers,
            json={"key_ids": [missing_id]},
        )
        assert r_partial.status_code == 200, r_partial.text
        partial = r_partial.json()
        assert partial["revoked"] == []
        assert len(partial["failed"]) == 1
        assert partial["failed"][0]["key_id"] == missing_id
        assert partial["failed"][0]["reason"] == "not_found"

    @pytest.mark.asyncio
    async def test_credential_summaries_member_includes_system_without_secrets(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """团队 member 可通过 summaries 解析 system 凭据名；完整列表仍不含 system。"""
        owner = test_user
        member = User(
            email=f"cred_sum_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Cred Summary Member",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Cred Summary Team", owner_user_id=owner.id)
        await ts.add_member(shared.id, member.id, "member")

        encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
        sys_name = f"sys-sum-{uuid.uuid4().hex[:8]}"
        sys_cred = await SystemProviderCredentialRepository(db_session).create(
            provider="openai",
            name=sys_name,
            api_key_encrypted=encrypt_value("sk-sys-summary-test-key", encryption_key),
            api_base="https://api.openai.com/v1",
        )
        await db_session.commit()

        owner_headers = auth_headers
        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {
            "Authorization": f"Bearer {member_token.access_token}",
            "X-Team-Id": str(shared.id),
        }

        team_cred_name = f"team-sum-{uuid.uuid4().hex[:8]}"
        r_team_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/credentials",
            headers=owner_headers,
            json={
                "provider": "openai",
                "name": team_cred_name,
                "api_key": "sk-team-summary-test-key-123456",
                "scope": "team",
            },
        )
        assert r_team_cred.status_code == 201, r_team_cred.text
        team_cred_id = r_team_cred.json()["id"]

        r_summaries = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/credentials/summaries",
            headers=member_headers,
        )
        assert r_summaries.status_code == 200, r_summaries.text
        summaries = r_summaries.json()
        by_id = {item["id"]: item for item in summaries}
        assert str(sys_cred.id) in by_id
        assert by_id[str(sys_cred.id)]["name"] == sys_name
        assert by_id[str(sys_cred.id)]["scope"] == "system"
        assert by_id[str(team_cred_id)]["name"] == team_cred_name
        assert by_id[str(team_cred_id)]["scope"] == "team"
        for item in summaries:
            assert "api_key_masked" not in item
            assert "api_base" not in item
            assert "extra" not in item
            assert "created_at" not in item

        r_list = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/credentials",
            headers=member_headers,
        )
        assert r_list.status_code == 200, r_list.text
        list_ids = {item["id"] for item in r_list.json()}
        assert str(team_cred_id) in list_ids
        assert str(sys_cred.id) not in list_ids

        r_sys_detail = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/credentials/{sys_cred.id}",
            headers=member_headers,
        )
        assert r_sys_detail.status_code == 403, r_sys_detail.text

    @pytest.mark.asyncio
    async def test_create_system_credential_returns_mapped_response(
        self,
        dev_client: AsyncClient,
        admin_user: User,
        admin_headers: dict[str, str],
        db_session,
    ) -> None:
        """POST scope=system：平台管理员创建系统凭据应 201 且响应含 scope=api 字段。"""
        team = await TeamService(db_session).ensure_personal_team(admin_user.id)
        await db_session.commit()

        sys_name = f"sys-create-{uuid.uuid4().hex[:8]}"
        r_create = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=admin_headers,
            json={
                "provider": "openai",
                "name": sys_name,
                "api_key": "sk-system-create-integration-test-key",
                "api_base": "https://api.openai.com/v1",
                "scope": "system",
            },
        )
        assert r_create.status_code == 201, r_create.text
        body = r_create.json()
        assert body["scope"] == "system"
        assert body["tenant_id"] is None
        assert body["name"] == sys_name
        assert body["provider"] == "openai"
        assert "api_key_masked" in body
        assert "sk-system-create-integration-test-key" not in body["api_key_masked"]

    @pytest.mark.asyncio
    async def test_batch_delete_system_models_partial_success(
        self,
        dev_client: AsyncClient,
        db_session,
    ) -> None:
        """POST /models/batch-delete：可删行成功，config-managed 进 failed[]。"""
        platform_admin = User(
            email=f"padmin_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Platform Admin",
            role="admin",
        )
        db_session.add(platform_admin)
        await db_session.commit()
        await db_session.refresh(platform_admin)

        team = await TeamService(db_session).ensure_personal_team(platform_admin.id)
        encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
        cred = await SystemProviderCredentialRepository(db_session).create(
            provider="openai",
            name=f"batch-del-cred-{uuid.uuid4().hex[:6]}",
            api_key_encrypted=encrypt_value("sk-fake", encryption_key),
            api_base=None,
        )
        await db_session.flush()
        deletable = SystemGatewayModel(
            name=f"batch-api-del-{uuid.uuid4().hex[:6]}",
            capability="chat",
            real_model="gpt-4o-mini",
            credential_id=cred.id,
            provider="openai",
        )
        managed = SystemGatewayModel(
            name=f"batch-api-managed-{uuid.uuid4().hex[:6]}",
            capability="chat",
            real_model="gpt-4o-mini",
            credential_id=cred.id,
            provider="openai",
            tags={GATEWAY_MODEL_MANAGED_BY_TAG: CONFIG_MANAGED_BY},
        )
        db_session.add_all([deletable, managed])
        await db_session.commit()

        uc = UserUseCase(db_session)
        admin_token = await uc.create_token(platform_admin)
        headers = {"Authorization": f"Bearer {admin_token.access_token}"}

        r = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models/batch-delete",
            headers=headers,
            json={"model_ids": [str(deletable.id), str(managed.id)]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert str(deletable.id) in body["succeeded"]
        assert len(body["failed"]) == 1
        assert body["failed"][0]["id"] == str(managed.id)

        r_list = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            params={"registry_scope": "system"},
        )
        assert r_list.status_code == 200, r_list.text
        ids = {m["id"] for m in _model_list_items(r_list.json())}
        assert str(deletable.id) not in ids
        assert str(managed.id) in ids

    @pytest.mark.asyncio
    async def test_resync_capabilities_updates_model_tags(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from domains.gateway.domain.litellm_capability_mapping import LitellmModelInfoHints
        from domains.gateway.infrastructure.litellm_capability_hint_adapter import (
            LitellmCapabilityHintAdapter,
        )

        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": f"resync-cred-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-resync-int-test-key-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        model_name = f"resync-{uuid.uuid4().hex[:6]}"
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            json={
                "name": model_name,
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cid,
                "provider": "openai",
                "tags": {"supports_vision": False},
            },
        )
        assert r_model.status_code == 201, r_model.text
        mid = r_model.json()["id"]

        def _vision_hints(_self, *, provider: str, real_model: str) -> LitellmModelInfoHints:
            _ = provider, real_model
            return LitellmModelInfoHints(supports_vision=True)

        monkeypatch.setattr(LitellmCapabilityHintAdapter, "get_model_hints", _vision_hints)

        r_patch = await dev_client.patch(
            f"/api/v1/gateway/teams/{team.id}/models/{mid}",
            headers=headers,
            json={"resync_capabilities": True},
        )
        assert r_patch.status_code == 200, r_patch.text
        body = r_patch.json()
        assert body["tags"]["supports_vision"] is True
        assert "image" in body["model_types"]

        await dev_client.delete(f"/api/v1/gateway/teams/{team.id}/models/{mid}", headers=headers)
        await dev_client.delete(f"/api/v1/gateway/teams/{team.id}/credentials/{cid}", headers=headers)

    @pytest.mark.asyncio
    async def test_resync_capabilities_rejects_config_managed_system_model(
        self,
        dev_client: AsyncClient,
        db_session,
    ) -> None:
        platform_admin = User(
            email=f"resync_admin_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Resync Admin",
            role="admin",
        )
        db_session.add(platform_admin)
        await db_session.commit()
        await db_session.refresh(platform_admin)

        team = await TeamService(db_session).ensure_personal_team(platform_admin.id)
        encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
        cred = await SystemProviderCredentialRepository(db_session).create(
            provider="openai",
            name=f"resync-managed-cred-{uuid.uuid4().hex[:6]}",
            api_key_encrypted=encrypt_value("sk-fake", encryption_key),
            api_base=None,
        )
        await db_session.flush()
        managed = SystemGatewayModel(
            name=f"resync-managed-{uuid.uuid4().hex[:6]}",
            capability="chat",
            real_model="gpt-4o-mini",
            credential_id=cred.id,
            provider="openai",
            tags={GATEWAY_MODEL_MANAGED_BY_TAG: CONFIG_MANAGED_BY},
        )
        db_session.add(managed)
        await db_session.commit()
        await db_session.refresh(managed)

        uc = UserUseCase(db_session)
        admin_token = await uc.create_token(platform_admin)
        headers = {"Authorization": f"Bearer {admin_token.access_token}"}

        r_patch = await dev_client.patch(
            f"/api/v1/gateway/teams/{team.id}/models/{managed.id}",
            headers=headers,
            json={"resync_capabilities": True},
        )
        assert r_patch.status_code == 400, r_patch.text
        assert "配置托管" in r_patch.json()["detail"]

    @pytest.mark.asyncio
    async def test_batch_resync_capabilities_partial_success(
        self,
        dev_client: AsyncClient,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /models/batch-resync-capabilities：可 resync 行成功，config-managed 进 failed[]。"""
        from domains.gateway.domain.litellm_capability_mapping import LitellmModelInfoHints
        from domains.gateway.infrastructure.litellm_capability_hint_adapter import (
            LitellmCapabilityHintAdapter,
        )

        platform_admin = User(
            email=f"batch_resync_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Batch Resync Admin",
            role="admin",
        )
        db_session.add(platform_admin)
        await db_session.commit()
        await db_session.refresh(platform_admin)

        team = await TeamService(db_session).ensure_personal_team(platform_admin.id)
        encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
        cred = await SystemProviderCredentialRepository(db_session).create(
            provider="openai",
            name=f"batch-resync-cred-{uuid.uuid4().hex[:6]}",
            api_key_encrypted=encrypt_value("sk-fake", encryption_key),
            api_base=None,
        )
        await db_session.flush()
        resyncable = SystemGatewayModel(
            name=f"batch-resync-ok-{uuid.uuid4().hex[:6]}",
            capability="chat",
            real_model="gpt-4o-mini",
            credential_id=cred.id,
            provider="openai",
            tags={"supports_vision": False},
        )
        managed = SystemGatewayModel(
            name=f"batch-resync-managed-{uuid.uuid4().hex[:6]}",
            capability="chat",
            real_model="gpt-4o-mini",
            credential_id=cred.id,
            provider="openai",
            tags={GATEWAY_MODEL_MANAGED_BY_TAG: CONFIG_MANAGED_BY},
        )
        db_session.add_all([resyncable, managed])
        await db_session.commit()

        def _vision_hints(_self, *, provider: str, real_model: str) -> LitellmModelInfoHints:
            _ = provider, real_model
            return LitellmModelInfoHints(supports_vision=True)

        monkeypatch.setattr(LitellmCapabilityHintAdapter, "get_model_hints", _vision_hints)

        uc = UserUseCase(db_session)
        admin_token = await uc.create_token(platform_admin)
        headers = {"Authorization": f"Bearer {admin_token.access_token}"}

        r = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models/batch-resync-capabilities",
            headers=headers,
            json={"model_ids": [str(resyncable.id), str(managed.id)]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert str(resyncable.id) in body["succeeded"]
        assert len(body["failed"]) == 1
        assert body["failed"][0]["id"] == str(managed.id)

        r_get = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models/{resyncable.id}",
            headers=headers,
        )
        assert r_get.status_code == 200, r_get.text
        assert r_get.json()["tags"]["supports_vision"] is True


@pytest.mark.integration
class TestGatewayFeaturesApi:
    @pytest.mark.asyncio
    async def test_features_reflects_global_guardrail_setting(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bootstrap.config import settings

        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers

        monkeypatch.setattr(settings, "gateway_default_guardrail_enabled", False)
        r_off = await dev_client.get(f"/api/v1/gateway/teams/{team.id}/features", headers=headers)
        assert r_off.status_code == 200, r_off.text
        assert r_off.json()["pii_guardrail_globally_enabled"] is False

        monkeypatch.setattr(settings, "gateway_default_guardrail_enabled", True)
        r_on = await dev_client.get(f"/api/v1/gateway/teams/{team.id}/features", headers=headers)
        assert r_on.status_code == 200, r_on.text
        assert r_on.json()["pii_guardrail_globally_enabled"] is True


@pytest.mark.integration
class TestGatewayPiiGuardrailCreateKey:
    @pytest.mark.asyncio
    async def test_create_key_rejects_guardrail_when_global_disabled(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bootstrap.config import settings

        monkeypatch.setattr(settings, "gateway_default_guardrail_enabled", False)
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers

        r = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/keys",
            headers=headers,
            json={"name": f"pii-off-{uuid.uuid4().hex[:6]}", "guardrail_enabled": True},
        )
        assert r.status_code == 400, r.text
        assert r.json().get("code") == "VALIDATION_ERROR"


@pytest.mark.integration
class TestManagedTeamCredentialsAggregateApi:
    @staticmethod
    async def _create_team_credential(
        dev_client: AsyncClient,
        team_id: uuid.UUID,
        headers: dict[str, str],
        *,
        name: str,
    ) -> dict:
        r = await dev_client.post(
            f"/api/v1/gateway/teams/{team_id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": name,
                "api_key": "sk-managed-aggregate-test-key",
                "api_base": None,
                "scope": "team",
            },
        )
        assert r.status_code == 201, r.text
        return r.json()

    @pytest.mark.asyncio
    async def test_list_managed_team_credentials_merges_writable_teams(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        ts = TeamService(db_session)
        personal = await ts.ensure_personal_team(test_user.id)
        shared = await ts.create_team(
            name=f"Aggregate-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()

        name_personal = f"personal-cred-{uuid.uuid4().hex[:6]}"
        name_shared = f"shared-cred-{uuid.uuid4().hex[:6]}"
        await self._create_team_credential(
            dev_client, personal.id, auth_headers, name=name_personal
        )
        await self._create_team_credential(
            dev_client, shared.id, auth_headers, name=name_shared
        )

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-credentials",
            headers=auth_headers,
            params={"page": 1, "page_size": 50},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["total"] >= 1
        assert payload["page"] == 1
        assert payload["page_size"] == 50
        assert "has_next" in payload
        assert "has_prev" in payload
        assert payload["queried_team_count"] >= 1
        assert payload["queried_personal_team_count"] == 0
        assert payload["queried_shared_team_count"] >= 1
        assert payload["queried_shared_team_count"] == payload["queried_team_count"]
        names = {item["name"] for item in payload["items"]}
        assert name_personal not in names
        assert name_shared in names
        assert all(item["scope"] == "team" for item in payload["items"])
        assert "tenant_ids_with_credentials" in payload
        assert isinstance(payload["tenant_ids_with_credentials"], list)
        assert len(payload["tenant_ids_with_credentials"]) >= 1

    @pytest.mark.asyncio
    async def test_list_managed_team_credentials_member_gets_empty(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        member = User(
            email=f"managed_cred_member_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Managed Cred Member",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(
            name=f"MemberOnly-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await ts.add_member(shared.id, member.id, "member")
        await db_session.commit()

        owner_cred_name = f"owner-only-{uuid.uuid4().hex[:6]}"
        await self._create_team_credential(
            dev_client,
            shared.id,
            auth_headers,
            name=owner_cred_name,
        )

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {"Authorization": f"Bearer {member_token.access_token}"}

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-credentials",
            headers=member_headers,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        names = {item["name"] for item in payload["items"]}
        assert owner_cred_name not in names
        assert payload["queried_team_count"] == 0
        assert payload["total"] == 0

    @pytest.mark.asyncio
    async def test_list_managed_team_credentials_search_filters_by_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        ts = TeamService(db_session)
        await ts.ensure_personal_team(test_user.id)
        unique = uuid.uuid4().hex[:8]
        shared = await ts.create_team(
            name=f"SearchTarget-{unique}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()

        target_name = f"search-hit-{uuid.uuid4().hex[:6]}"
        await self._create_team_credential(
            dev_client, shared.id, auth_headers, name=target_name
        )

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-credentials",
            headers=auth_headers,
            params={"search": f"SearchTarget-{unique}", "page_size": 50},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["queried_team_count"] == 1
        names = {item["name"] for item in payload["items"]}
        assert target_name in names

    @pytest.mark.asyncio
    async def test_list_managed_team_credentials_unauthenticated(
        self,
        dev_client: AsyncClient,
    ) -> None:
        r = await dev_client.get("/api/v1/gateway/managed-team-credentials")
        assert r.status_code == 401, r.text

    @pytest.mark.asyncio
    async def test_list_managed_team_credentials_platform_admin_excludes_anonymous_personal(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        db_session,
    ) -> None:
        anon = User(
            email=f"anon_cred_{uuid.uuid4()}@anonymous.local",
            hashed_password="x",
            name="Anon",
            role="anonymous",
        )
        db_session.add(anon)
        await db_session.commit()
        await db_session.refresh(anon)
        await TeamService(db_session).ensure_personal_team(anon.id)
        await db_session.commit()

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-credentials",
            headers=admin_headers,
            params={"page": 1, "page_size": 10},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert "queried_personal_team_count" in payload
        assert "queried_shared_team_count" in payload
        assert payload["queried_personal_team_count"] == 0
        assert payload["queried_shared_team_count"] == payload["queried_team_count"]

    @pytest.mark.asyncio
    async def test_list_managed_team_credentials_pagination_has_next(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        ts = TeamService(db_session)
        shared = await ts.create_team(
            name=f"PageCred-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()

        page_size = 3
        created_names: list[str] = []
        for i in range(page_size + 1):
            name = f"page-cred-{uuid.uuid4().hex[:6]}-{i}"
            created_names.append(name)
            await self._create_team_credential(
                dev_client, shared.id, auth_headers, name=name
            )

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-credentials",
            headers=auth_headers,
            params={"page": 1, "page_size": page_size},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["page"] == 1
        assert payload["page_size"] == page_size
        assert payload["total"] >= page_size + 1
        assert payload["has_next"] is True
        assert payload["has_prev"] is False
        assert len(payload["items"]) == page_size

        r2 = await dev_client.get(
            "/api/v1/gateway/managed-team-credentials",
            headers=auth_headers,
            params={"page": 2, "page_size": page_size},
        )
        assert r2.status_code == 200, r2.text
        payload2 = r2.json()
        assert payload2["has_prev"] is True
        assert len(payload2["items"]) >= 1


class TestManagedTeamModelsAggregateApi:
    async def _create_team_model(
        self,
        dev_client: AsyncClient,
        team_id: uuid.UUID,
        headers: dict[str, str],
        *,
        model_name: str,
    ) -> dict[str, object]:
        cred_name = f"cred-{uuid.uuid4().hex[:6]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team_id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": cred_name,
                "api_key": "sk-managed-models-aggregate-test-key",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team_id}/models",
            headers=headers,
            json={
                "name": model_name,
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cid,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text
        return r_model.json()

    @pytest.mark.asyncio
    async def test_list_managed_team_models_excludes_personal_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        ts = TeamService(db_session)
        personal = await ts.ensure_personal_team(test_user.id)
        shared = await ts.create_team(
            name=f"ModelsAgg-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()

        personal_model = f"personal-model-{uuid.uuid4().hex[:6]}"
        shared_model = f"shared-model-{uuid.uuid4().hex[:6]}"
        await self._create_team_model(
            dev_client, personal.id, auth_headers, model_name=personal_model
        )
        await self._create_team_model(
            dev_client, shared.id, auth_headers, model_name=shared_model
        )

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-models",
            headers=auth_headers,
            params={"page": 1, "page_size": 50},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        names = {item["name"] for item in payload["items"]}
        assert personal_model not in names
        assert shared_model in names
        assert payload["queried_personal_team_count"] == 0
        assert payload["queried_shared_team_count"] >= 1
        assert "tenant_ids_with_models" in payload
        assert str(shared.id) in {str(t) for t in payload["tenant_ids_with_models"]}
