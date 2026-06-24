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
from domains.gateway.domain.types import (
    CONFIG_MANAGED_BY,
    CREDENTIAL_CASCADE_DISABLED_TAG,
    GATEWAY_MODEL_MANAGED_BY_TAG,
)
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


def _quota_rule_list_items(body: dict | list) -> list:
    if isinstance(body, list):
        return body
    return body["items"]


_PAGINATED_ENVELOPE_KEYS = ("items", "total", "page", "page_size", "has_next", "has_prev")


def _assert_paginated_envelope(payload: dict, *, page: int, page_size: int) -> None:
    for key in _PAGINATED_ENVELOPE_KEYS:
        assert key in payload, f"missing pagination field: {key}"
    assert payload["page"] == page
    assert payload["page_size"] == page_size
    assert isinstance(payload["has_next"], bool)
    assert isinstance(payload["has_prev"], bool)


async def _create_team_model_via_api(
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
            "api_key": "sk-usage-summary-test-key",
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
    async def test_list_invite_candidates_paginated(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        invitee = User(
            email=f"candidate_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Candidate Person",
        )
        db_session.add(invitee)
        await db_session.commit()
        await db_session.refresh(invitee)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Candidates Team", owner_user_id=test_user.id)
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/members/candidates",
            headers=auth_headers,
            params={"search": "Candidate", "page": 1, "page_size": 20},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        ids = [item["id"] for item in data["items"]]
        assert str(invitee.id) in ids
        assert str(test_user.id) not in ids
        assert "role" not in data["items"][0]
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total"] >= 1
        assert "has_next" in data
        assert "has_prev" in data

    @pytest.mark.asyncio
    async def test_list_invite_candidates_excludes_existing_member(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        member = User(
            email=f"existing_member_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Existing Member",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Exclude Member Team", owner_user_id=test_user.id)
        await ts.add_member(shared.id, member.id, "member")
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/members/candidates",
            headers=auth_headers,
            params={"search": member.email.split("@")[0]},
        )
        assert r.status_code == 200, r.text
        ids = [item["id"] for item in r.json()["items"]]
        assert str(member.id) not in ids

    @pytest.mark.asyncio
    async def test_list_invite_candidates_shared_teams_scope(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        outsider = User(
            email=f"outsider_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Outsider User",
        )
        insider = User(
            email=f"insider_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Insider User",
        )
        db_session.add_all([outsider, insider])
        await db_session.commit()
        await db_session.refresh(outsider)
        await db_session.refresh(insider)

        ts = TeamService(db_session)
        bridge = await ts.create_team(name="Bridge Team", owner_user_id=test_user.id)
        await ts.add_member(bridge.id, insider.id, "member")
        target = await ts.create_team(name="Target Team", owner_user_id=test_user.id)
        await ts.update_team(
            target.id,
            settings={"invite_candidate_scope": "shared_teams"},
            actor_team_role="owner",
        )
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{target.id}/members/candidates",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        ids = {item["id"] for item in r.json()["items"]}
        assert str(insider.id) in ids
        assert str(outsider.id) not in ids

    @pytest.mark.asyncio
    async def test_list_invite_candidates_forbidden_for_member(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        member = User(
            email=f"cand_member_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Cand Member",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Cand Forbidden Team", owner_user_id=test_user.id)
        await ts.add_member(shared.id, member.id, "member")
        await db_session.commit()

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {
            "Authorization": f"Bearer {member_token.access_token}",
            "X-Team-Id": str(shared.id),
        }

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/members/candidates",
            headers=member_headers,
        )
        assert r.status_code == 403, r.text

    @pytest.mark.asyncio
    async def test_update_invite_scope_forbidden_for_team_admin(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team_admin = User(
            email=f"team_admin_scope_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Team Admin Scope",
        )
        db_session.add(team_admin)
        await db_session.commit()
        await db_session.refresh(team_admin)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Scope Settings Team", owner_user_id=test_user.id)
        await ts.add_member(shared.id, team_admin.id, "admin")
        await db_session.commit()

        admin_uc = UserUseCase(db_session)
        admin_token = await admin_uc.create_token(team_admin)
        admin_headers = {
            "Authorization": f"Bearer {admin_token.access_token}",
            "X-Team-Id": str(shared.id),
        }

        r = await dev_client.patch(
            f"/api/v1/gateway/teams/{shared.id}",
            headers=admin_headers,
            json={"settings": {"invite_candidate_scope": "shared_teams"}},
        )
        assert r.status_code == 403, r.text

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
        logs_payload = logs.json()
        _assert_paginated_envelope(logs_payload, page=1, page_size=10)
        ids = {item["id"] for item in logs_payload["items"]}
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
    async def test_platform_usage_aggregation_admin_only_and_cross_tenant(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """usage_aggregation=platform：仅平台管理员；全平台轴可聚合多 tenant 日志。"""
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
        shared = await ts.create_team(name="Platform Agg Team", owner_user_id=owner.id)
        await ts.add_member(shared.id, member.id, "member")
        member_personal = await ts.ensure_personal_team(member.id)

        now = datetime.now(UTC)
        log_shared = uuid.uuid4()
        log_personal = uuid.uuid4()
        db_session.add_all(
            [
                GatewayRequestLog(
                    id=log_shared,
                    created_at=now,
                    tenant_id=shared.id,
                    user_id=owner.id,
                    vkey_id=None,
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
                    request_id=f"plat-agg-shared-{uuid.uuid4().hex[:8]}",
                ),
                GatewayRequestLog(
                    id=log_personal,
                    created_at=now,
                    tenant_id=member_personal.id,
                    user_id=member.id,
                    vkey_id=None,
                    capability="chat",
                    route_name=None,
                    real_model="gpt-4",
                    provider="openai",
                    status="success",
                    input_tokens=2,
                    output_tokens=2,
                    cached_tokens=0,
                    cost_usd=Decimal("0.002"),
                    latency_ms=10,
                    cache_hit=False,
                    fallback_chain=[],
                    request_id=f"plat-agg-personal-{uuid.uuid4().hex[:8]}",
                ),
            ]
        )
        await db_session.commit()

        owner_headers = auth_headers
        uc = UserUseCase(db_session)
        admin_token = await uc.create_token(platform_admin)
        admin_headers = {"Authorization": f"Bearer {admin_token.access_token}"}

        r_owner_platform = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/dashboard/summary",
            params={"usage_aggregation": "platform", "days": 1},
            headers=owner_headers,
        )
        assert r_owner_platform.status_code == 403, r_owner_platform.text

        r_admin_logs = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/logs",
            params={"usage_aggregation": "platform", "page": 1, "page_size": 200},
            headers=admin_headers,
        )
        assert r_admin_logs.status_code == 200, r_admin_logs.text
        admin_log_ids = {item["id"] for item in r_admin_logs.json()["items"]}
        assert str(log_shared) in admin_log_ids
        assert str(log_personal) in admin_log_ids

        r_admin_summary = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/dashboard/summary",
            params={"usage_aggregation": "platform", "days": 1},
            headers=admin_headers,
        )
        assert r_admin_summary.status_code == 200, r_admin_summary.text
        assert int(r_admin_summary.json()["total_requests"]) >= 2

        r_owner_workspace = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/dashboard/summary",
            params={"usage_aggregation": "workspace", "days": 1},
            headers=owner_headers,
        )
        assert r_owner_workspace.status_code == 200, r_owner_workspace.text
        assert r_owner_workspace.json()["total_requests"] == 1

        # 路径 {team_id} 不得隐式写入 ?filter_team_id= 筛选（否则 platform 会被收窄为单团队）
        r_admin_stats = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/dashboard/statistics",
            params={
                "usage_aggregation": "platform",
                "group_by": "user",
                "days": 1,
                "page": 1,
                "page_size": 50,
            },
            headers=admin_headers,
        )
        assert r_admin_stats.status_code == 200, r_admin_stats.text
        stats_body = r_admin_stats.json()
        assert int(stats_body["totals"]["requests"]) >= 2
        user_keys = {item["group_key"] for item in stats_body["items"]}
        assert str(member.id) in user_keys

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
        r_all = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models/presets", headers=headers
        )
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

        r_get = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/credentials/{cid}", headers=headers
        )
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
    async def test_member_owned_team_credential_admin_cannot_reveal_but_can_update_and_delete_model(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """成员创建者私有凭据：admin 不可 reveal；admin 可启停/删关联模型。"""
        member = User(
            email=f"priv_cred_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Private Cred Member",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(
            name=f"PrivateCred-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await ts.add_member(shared.id, member.id, "member")
        await db_session.commit()

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {
            "Authorization": f"Bearer {member_token.access_token}",
            "X-Team-Id": str(shared.id),
        }
        owner_headers = {
            **auth_headers,
            "X-Team-Id": str(shared.id),
        }

        cred_name = f"member-owned-{uuid.uuid4().hex[:6]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/credentials",
            headers=member_headers,
            json={
                "provider": "openai",
                "name": cred_name,
                "api_key": "sk-member-owned-test-key-123456",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_body = r_cred.json()
        cid = cred_body["id"]
        assert cred_body.get("created_by_user_id") == str(member.id)

        r_owner_get = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/credentials/{cid}",
            headers=owner_headers,
        )
        assert r_owner_get.status_code == 404, r_owner_get.text

        r_owner_reveal = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/credentials/{cid}/reveal",
            headers=owner_headers,
        )
        assert r_owner_reveal.status_code == 404, r_owner_reveal.text

        model_name = f"member-model-{uuid.uuid4().hex[:6]}"
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/models",
            headers=member_headers,
            json={
                "name": model_name,
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cid,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text
        mid = r_model.json()["id"]

        r_owner_create = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/models",
            headers=owner_headers,
            json={
                "name": f"blocked-{uuid.uuid4().hex[:6]}",
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cid,
                "provider": "openai",
            },
        )
        assert r_owner_create.status_code == 404, r_owner_create.text

        r_owner_disable = await dev_client.patch(
            f"/api/v1/gateway/teams/{shared.id}/models/{mid}",
            headers=owner_headers,
            json={"enabled": False},
        )
        assert r_owner_disable.status_code == 200, r_owner_disable.text
        assert r_owner_disable.json()["enabled"] is False

        r_owner_enable = await dev_client.patch(
            f"/api/v1/gateway/teams/{shared.id}/models/{mid}",
            headers=owner_headers,
            json={"enabled": True},
        )
        assert r_owner_enable.status_code == 200, r_owner_enable.text
        assert r_owner_enable.json()["enabled"] is True

        r_owner_delete = await dev_client.delete(
            f"/api/v1/gateway/teams/{shared.id}/models/{mid}",
            headers=owner_headers,
        )
        assert r_owner_delete.status_code == 204, r_owner_delete.text

        r_member_reveal = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/credentials/{cid}/reveal",
            headers=member_headers,
        )
        assert r_member_reveal.status_code == 200, r_member_reveal.text
        assert r_member_reveal.json()["api_key"] == "sk-member-owned-test-key-123456"

    @pytest.mark.asyncio
    async def test_member_private_credential_model_list_filter_respects_visibility(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """成员私有凭据：他人 credential_id 筛选 404；q 凭据名不得命中；创建者可筛到。"""
        member = User(
            email=f"priv_model_filter_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Private Model Filter Member",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(
            name=f"PrivModelFilter-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await ts.add_member(shared.id, member.id, "member")
        await db_session.commit()

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {
            "Authorization": f"Bearer {member_token.access_token}",
            "X-Team-Id": str(shared.id),
        }
        owner_headers = {
            **auth_headers,
            "X-Team-Id": str(shared.id),
        }

        cred_name = f"priv-filter-{uuid.uuid4().hex[:6]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/credentials",
            headers=member_headers,
            json={
                "provider": "openai",
                "name": cred_name,
                "api_key": "sk-priv-filter-test-key-123456",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]

        model_name = f"priv-model-{uuid.uuid4().hex[:6]}"
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/models",
            headers=member_headers,
            json={
                "name": model_name,
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cid,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text

        r_owner_by_cred = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/models",
            headers=owner_headers,
            params={"credential_id": cid, "page": 1, "page_size": 50},
        )
        assert r_owner_by_cred.status_code == 404, r_owner_by_cred.text

        r_owner_by_q = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/models",
            headers=owner_headers,
            params={"q": cred_name, "page": 1, "page_size": 50},
        )
        assert r_owner_by_q.status_code == 200, r_owner_by_q.text
        owner_names = {m["name"] for m in _model_list_items(r_owner_by_q.json())}
        assert model_name not in owner_names

        r_member_by_cred = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/models",
            headers=member_headers,
            params={"credential_id": cid, "page": 1, "page_size": 50},
        )
        assert r_member_by_cred.status_code == 200, r_member_by_cred.text
        member_names = {m["name"] for m in _model_list_items(r_member_by_cred.json())}
        assert model_name in member_names

        r_managed_owner = await dev_client.get(
            "/api/v1/gateway/managed-team-models",
            headers=owner_headers,
            params={"credential_id": cid, "page": 1, "page_size": 50},
        )
        assert r_managed_owner.status_code == 404, r_managed_owner.text

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
        for key in (
            "items",
            "total",
            "page",
            "page_size",
            "has_next",
            "has_prev",
            "connectivity_summary",
        ):
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
    async def test_list_team_models_filters_by_credential_name_q(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """GET .../models?q= 可匹配绑定凭据的展示名。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        unique_cred = f"Acme-Prod-{uuid.uuid4().hex[:8]}"
        other_cred = f"Other-Key-{uuid.uuid4().hex[:8]}"
        matched_alias = f"matched-{uuid.uuid4().hex[:6]}"
        other_alias = f"other-{uuid.uuid4().hex[:6]}"

        for cred_name, alias in ((unique_cred, matched_alias), (other_cred, other_alias)):
            r_cred = await dev_client.post(
                f"/api/v1/gateway/teams/{team.id}/credentials",
                headers=headers,
                json={
                    "provider": "openai",
                    "name": cred_name,
                    "api_key": "sk-cred-name-filter-test-key-123456789",
                    "scope": "team",
                },
            )
            assert r_cred.status_code == 201, r_cred.text
            cid = r_cred.json()["id"]
            r_model = await dev_client.post(
                f"/api/v1/gateway/teams/{team.id}/models",
                headers=headers,
                json={
                    "name": alias,
                    "capability": "chat",
                    "real_model": "gpt-4o-mini",
                    "credential_id": cid,
                    "provider": "openai",
                },
            )
            assert r_model.status_code == 201, r_model.text

        r_q = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            params={"q": unique_cred, "page_size": 50},
        )
        assert r_q.status_code == 200, r_q.text
        names = {m["name"] for m in _model_list_items(r_q.json())}
        assert matched_alias in names
        assert other_alias not in names

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
    async def test_list_system_requestable_models_paginated_envelope(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """成员系统浏览：system_requestable 分页 envelope，且仅 system registry_kind。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=auth_headers,
            params={"registry_scope": "system_requestable", "page": 1, "page_size": 5},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        for key in (
            "items",
            "total",
            "page",
            "page_size",
            "has_next",
            "has_prev",
            "connectivity_summary",
        ):
            assert key in body
        assert body["page"] == 1
        assert body["page_size"] == 5
        assert all(item.get("registry_kind") == "system" for item in body["items"])
        summary = body["connectivity_summary"]
        assert summary["total"] == body["total"]

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
        for key in (
            "items",
            "total",
            "page",
            "page_size",
            "has_next",
            "has_prev",
            "connectivity_summary",
        ):
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
        model_body["id"]
        assert model_body["tenant_id"] == str(team.id)
        assert model_body["team_id"] == str(team.id)

        r_del = await dev_client.delete(
            f"/api/v1/gateway/teams/{team.id}/credentials/{cid}", headers=headers
        )
        assert r_del.status_code == 204, r_del.text

        r_cred_after = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/credentials/{cid}", headers=headers
        )
        assert r_cred_after.status_code == 404

        r_models_after = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            params={"credential_id": cid},
        )
        assert r_models_after.status_code == 404, r_models_after.text
        assert r_models_after.json()["code"] == "CREDENTIAL_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_patch_credential_is_active_false_cascades_model_enabled(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """PATCH 停用凭据时，关联模型 enabled=false 并打 disabled_by_credential 标。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        cred_name = f"inactive-cascade-{uuid.uuid4().hex[:8]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": cred_name,
                "api_key": "sk-int-inactive-cascade-key-12345678",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        model_name = f"vm-inact-{uuid.uuid4().hex[:6]}"
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
        mid = r_model.json()["id"]

        r_off = await dev_client.patch(
            f"/api/v1/gateway/teams/{team.id}/credentials/{cid}",
            headers=headers,
            json={"is_active": False},
        )
        assert r_off.status_code == 200, r_off.text
        assert r_off.json()["is_active"] is False

        r_get = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models/{mid}",
            headers=headers,
        )
        assert r_get.status_code == 200, r_get.text
        body = r_get.json()
        assert body["enabled"] is False
        assert body.get("tags", {}).get(CREDENTIAL_CASCADE_DISABLED_TAG) is True

        r_on = await dev_client.patch(
            f"/api/v1/gateway/teams/{team.id}/credentials/{cid}",
            headers=headers,
            json={"is_active": True},
        )
        assert r_on.status_code == 200, r_on.text

        r_restored = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models/{mid}",
            headers=headers,
        )
        assert r_restored.status_code == 200, r_restored.text
        restored = r_restored.json()
        assert restored["enabled"] is True
        assert CREDENTIAL_CASCADE_DISABLED_TAG not in (restored.get("tags") or {})

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
    async def test_team_create_model_with_display_name(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """团队 POST /models：display_name 写入 tags.display_name，name 仍为调用名。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": f"disp-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-display-name-int-test-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        invoke_name = f"alias-{uuid.uuid4().hex[:6]}"
        display_name = "通义千问 Max 展示"
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            json={
                "name": invoke_name,
                "display_name": display_name,
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cid,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text
        body = r_model.json()
        assert body["name"] == invoke_name
        assert (body.get("tags") or {}).get("display_name") == display_name

    @pytest.mark.asyncio
    async def test_team_patch_model_display_name(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """PATCH /models/{id}：仅改 display_name 时调用名不变。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": f"patch-disp-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-patch-display-int-test-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        invoke_name = f"alias-{uuid.uuid4().hex[:6]}"
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            json={
                "name": invoke_name,
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cid,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text
        mid = r_model.json()["id"]
        new_display = "更新后的展示名"
        r_patch = await dev_client.patch(
            f"/api/v1/gateway/teams/{team.id}/models/{mid}",
            headers=headers,
            json={"display_name": new_display},
        )
        assert r_patch.status_code == 200, r_patch.text
        patched = r_patch.json()
        assert patched["name"] == invoke_name
        assert (patched.get("tags") or {}).get("display_name") == new_display

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
        assert "moonshot.coding_plan" in ids
        kimi_code = next(p for p in profiles if p["id"] == "moonshot.coding_plan")
        assert kimi_code["api_bases"]["openai_compat"] == "https://api.kimi.com/coding/v1"

    @pytest.mark.asyncio
    async def test_create_managed_credential_moonshot_coding_plan(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """Moonshot Kimi Code：profile_id 与默认 api_base 正确落库。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        name = f"ms-cp-{uuid.uuid4().hex[:8]}"
        r = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "moonshot",
                "name": name,
                "api_key": "sk-int-test-moonshot-key-1234567890",
                "profile_id": "moonshot.coding_plan",
                "scope": "team",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["provider"] == "moonshot"
        assert body["profile_id"] == "moonshot.coding_plan"
        assert body["effective_api_base_openai"] == "https://api.kimi.com/coding/v1"

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
    async def test_my_models_batch_resync_capabilities_partial_success(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /my-models/batch-resync-capabilities：可 resync 行成功，未知 id 进 failed[]。"""
        from domains.gateway.domain.litellm_capability_mapping import LitellmModelInfoHints
        from domains.gateway.infrastructure.litellm_capability_hint_adapter import (
            LitellmCapabilityHintAdapter,
        )

        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"my-resync-cred-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-my-resync-int-test-key-123456",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_id = r_cred.json()["id"]

        r_create = await dev_client.post(
            "/api/v1/gateway/my-models",
            headers=auth_headers,
            json={
                "display_name": "Resync Test",
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "credential_id": cred_id,
                "model_types": ["text"],
            },
        )
        assert r_create.status_code == 201, r_create.text
        model_id = r_create.json()[0]["id"]
        unknown_id = str(uuid.uuid4())

        def _vision_hints(_self, *, provider: str, real_model: str) -> LitellmModelInfoHints:
            _ = provider, real_model
            return LitellmModelInfoHints(supports_vision=True)

        monkeypatch.setattr(LitellmCapabilityHintAdapter, "get_model_hints", _vision_hints)

        r = await dev_client.post(
            "/api/v1/gateway/my-models/batch-resync-capabilities",
            headers=auth_headers,
            json={"model_ids": [model_id, unknown_id]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert model_id in body["succeeded"]
        assert len(body["failed"]) == 1
        assert body["failed"][0]["id"] == unknown_id

    @pytest.mark.asyncio
    async def test_my_models_usage_summary_pagination_and_route_names(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """GET /my-models/usage-summary：个人轴按 route_name 聚合。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()

        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"my-usage-cred-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-my-usage-int-test-key-123456",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_id = r_cred.json()["id"]

        route_a = None
        route_b = None
        for display_name in ("Usage A", "Usage B"):
            r_create = await dev_client.post(
                "/api/v1/gateway/my-models",
                headers=auth_headers,
                json={
                    "display_name": display_name,
                    "provider": "openai",
                    "model_id": f"gpt-4o-mini-{uuid.uuid4().hex[:4]}",
                    "credential_id": cred_id,
                    "model_types": ["text"],
                },
            )
            assert r_create.status_code == 201, r_create.text
            created = r_create.json()[0]
            if display_name == "Usage A":
                route_a = created["name"]
            else:
                route_b = created["name"]
        assert route_a and route_b

        now = datetime.now(UTC)
        db_session.add(
            GatewayRequestLog(
                id=uuid.uuid4(),
                created_at=now,
                tenant_id=team.id,
                user_id=test_user.id,
                vkey_id=None,
                capability="chat",
                route_name=route_a,
                real_model="gpt-4o-mini",
                provider="openai",
                status="success",
                input_tokens=5,
                output_tokens=3,
                cached_tokens=0,
                cost_usd=Decimal("0.002"),
                latency_ms=50,
                cache_hit=False,
                fallback_chain=[],
                request_id="req-my-usage-a",
            )
        )
        await db_session.commit()

        r_page = await dev_client.get(
            "/api/v1/gateway/my-models/usage-summary",
            headers=auth_headers,
            params={"days": 7, "page": 1, "page_size": 1},
        )
        assert r_page.status_code == 200, r_page.text
        page_payload = r_page.json()
        _assert_paginated_envelope(page_payload, page=1, page_size=1)
        assert page_payload["total"] >= 2
        assert page_payload["has_next"] is True
        assert "start" in page_payload
        assert "end" in page_payload

        r_scoped = await dev_client.get(
            "/api/v1/gateway/my-models/usage-summary",
            headers=auth_headers,
            params={"days": 7, "route_names": [route_a]},
        )
        assert r_scoped.status_code == 200, r_scoped.text
        scoped_payload = r_scoped.json()
        _assert_paginated_envelope(scoped_payload, page=1, page_size=20)
        assert len(scoped_payload["items"]) == 1
        assert scoped_payload["items"][0]["route_name"] == route_a
        assert scoped_payload["items"][0]["workspace"]["requests"] >= 1

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
    async def test_entitlement_plan_management_apis(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """EntitlementPlan 管理 API 与 usage/margin 读入口。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        now = datetime.now(UTC).replace(microsecond=0)
        valid_from = (now - timedelta(minutes=1)).isoformat()
        valid_until = (now + timedelta(days=30)).isoformat()

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
    async def test_upstream_quota_rules_readable_by_credential_owner_member(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """凭据创建者（非 admin 成员）可在配额中心看到本人凭据的上游规则。"""
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
        shared = await ts.create_team(name="Upstream Quota Read Team", owner_user_id=owner.id)
        await ts.add_member(shared.id, member.id, "member")
        await db_session.commit()

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {
            "Authorization": f"Bearer {member_token.access_token}",
            "X-Team-Id": str(shared.id),
        }

        real_model = "openai/gpt-4o-mini"

        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/credentials",
            headers=member_headers,
            json={
                "provider": "openai",
                "name": f"member-cred-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-member-quota-read-test",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        credential_id = r_cred.json()["id"]

        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/models",
            headers=member_headers,
            json={
                "name": f"member-model-{uuid.uuid4().hex[:8]}",
                "capability": "chat",
                "real_model": real_model,
                "credential_id": credential_id,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text

        r_batch = await dev_client.put(
            f"/api/v1/gateway/teams/{shared.id}/quota-rules/batch",
            headers=auth_headers,
            json={
                "rules": [
                    {
                        "layer": "upstream",
                        "credential_id": credential_id,
                        "model_name": real_model,
                        "window_seconds": 86400,
                        "quota_label": "daily",
                        "reset_strategy": "calendar_daily_utc",
                        "limit_requests": 100,
                    }
                ]
            },
        )
        assert r_batch.status_code == 200, r_batch.text
        assert r_batch.json()["failed"] == []

        r_list = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/quota-rules",
            headers=member_headers,
            params={"layer": "upstream", "credential_id": credential_id},
        )
        assert r_list.status_code == 200, r_list.text
        assert len(_quota_rule_list_items(r_list.json())) == 1

    @pytest.mark.asyncio
    async def test_plan_apis_reject_cross_team_access(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """EntitlementPlan / api-key-grant entitlements API 跨团队应返回 404。

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
        real_model = "openai/gpt-4o-mini"

        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team_a.id}/models",
            headers=headers_a,
            json={
                "name": f"cross-team-model-{uuid.uuid4().hex[:8]}",
                "capability": "chat",
                "real_model": real_model,
                "credential_id": credential_id,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text

        r_quota_batch = await dev_client.put(
            f"/api/v1/gateway/teams/{team_a.id}/quota-rules/batch",
            headers=headers_a,
            json={
                "rules": [
                    {
                        "layer": "upstream",
                        "credential_id": credential_id,
                        "model_name": real_model,
                        "window_seconds": 86400,
                        "quota_label": "daily",
                        "reset_strategy": "calendar_daily_utc",
                        "limit_requests": 100,
                    }
                ]
            },
        )
        assert r_quota_batch.status_code == 200, r_quota_batch.text
        quota_id = r_quota_batch.json()["succeeded"][0]["source_ref"]["quota_id"]

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
                "quotas": [{"label": "daily", "window_seconds": 86400, "limit_requests": 10}],
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

        r1 = await dev_client.put(
            f"/api/v1/gateway/teams/{team_b.id}/quota-rules/batch",
            headers=headers_b,
            json={
                "rules": [
                    {
                        "layer": "upstream",
                        "credential_id": credential_id,
                        "model_name": real_model,
                        "window_seconds": 86400,
                        "quota_label": "daily",
                        "limit_requests": 1,
                    }
                ]
            },
        )
        assert r1.status_code == 200, r1.text
        assert len(r1.json()["failed"]) == 1, r1.text

        r2 = await dev_client.post(
            f"/api/v1/gateway/teams/{team_b.id}/quota-rules/usage-adjustments",
            headers=headers_b,
            json={
                "layer": "upstream",
                "quota_id": quota_id,
                "mode": "set",
                "current_usd": "1.00",
            },
        )
        assert r2.status_code == 404, r2.text

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
                "quotas": [{"label": "daily", "window_seconds": 86400, "limit_requests": 1}],
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

        r_owner_list = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/keys", headers=owner_headers
        )
        assert r_owner_list.status_code == 200, r_owner_list.text
        owner_ids = {item["id"] for item in r_owner_list.json()}
        assert owner_ids == {owner_key_id}

        r_member_list = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/keys", headers=member_headers
        )
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
        assert str(team_cred_id) in by_id
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
        list_by_id = {item["id"]: item for item in r_list.json()}
        assert str(team_cred_id) in list_by_id
        assert list_by_id[str(team_cred_id)]["management_access"] == "metadata"
        assert str(sys_cred.id) not in list_by_id

        r_sys_detail = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/credentials/{sys_cred.id}",
            headers=member_headers,
        )
        assert r_sys_detail.status_code == 404, r_sys_detail.text

    @pytest.mark.asyncio
    async def test_playground_credential_summaries_membership_scope(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """Playground 聚合：仅 membership 内 active 凭据，且含 context_team_id。"""
        owner = test_user
        member = User(
            email=f"pg_cred_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Playground Cred Member",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(name="Playground Cred Team", owner_user_id=owner.id)
        await ts.add_member(shared.id, member.id, "member")

        active_name = f"pg-active-{uuid.uuid4().hex[:8]}"
        r_active = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": active_name,
                "api_key": "sk-pg-active-test-key-123456",
                "scope": "team",
            },
        )
        assert r_active.status_code == 201, r_active.text
        active_id = r_active.json()["id"]

        inactive_name = f"pg-inactive-{uuid.uuid4().hex[:8]}"
        r_inactive = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": inactive_name,
                "api_key": "sk-pg-inactive-test-key-123456",
                "scope": "team",
            },
        )
        assert r_inactive.status_code == 201, r_inactive.text
        inactive_id = r_inactive.json()["id"]
        r_off = await dev_client.patch(
            f"/api/v1/gateway/teams/{shared.id}/credentials/{inactive_id}",
            headers=auth_headers,
            json={"is_active": False},
        )
        assert r_off.status_code == 200, r_off.text

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {"Authorization": f"Bearer {member_token.access_token}"}

        my_name = f"pg-my-{uuid.uuid4().hex[:8]}"
        r_my = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=member_headers,
            json={
                "provider": "openai",
                "name": my_name,
                "api_key": "sk-pg-my-test-key-123456",
            },
        )
        assert r_my.status_code == 201, r_my.text
        my_cred_id = r_my.json()["id"]

        member_team_name = f"pg-member-team-{uuid.uuid4().hex[:8]}"
        r_member_team = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/credentials",
            headers=member_headers,
            json={
                "provider": "openai",
                "name": member_team_name,
                "api_key": "sk-pg-member-team-key-123456",
                "scope": "team",
            },
        )
        assert r_member_team.status_code == 201, r_member_team.text
        member_team_id = r_member_team.json()["id"]

        r_pg = await dev_client.get(
            "/api/v1/gateway/playground/credential-summaries",
            headers=member_headers,
        )
        assert r_pg.status_code == 200, r_pg.text
        rows = r_pg.json()
        by_id = {item["id"]: item for item in rows}
        assert active_id in by_id
        assert by_id[active_id]["context_team_id"] == str(shared.id)
        assert by_id[active_id]["scope"] == "team"
        assert inactive_id not in by_id
        assert member_team_id in by_id
        assert by_id[member_team_id]["context_team_id"] == str(shared.id)
        assert by_id[member_team_id]["scope"] == "team"
        assert my_cred_id in by_id
        assert by_id[my_cred_id]["scope"] == "user"
        assert inactive_id not in by_id
        for item in rows:
            assert "context_team_id" in item
            assert item["is_active"] is True
            assert "api_key_masked" not in item

    @pytest.mark.asyncio
    async def test_playground_credential_summaries_admin_excludes_non_membership_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """平台 admin 亦仅聚合 membership；非成员团队凭据不可见。"""
        ts = TeamService(db_session)
        foreign = await ts.create_team(name="Foreign PG Team", owner_user_id=test_user.id)
        await db_session.commit()

        foreign_name = f"pg-foreign-{uuid.uuid4().hex[:8]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{foreign.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": foreign_name,
                "api_key": "sk-pg-foreign-test-key-123456",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        foreign_cred_id = r_cred.json()["id"]

        r_pg = await dev_client.get(
            "/api/v1/gateway/playground/credential-summaries",
            headers=admin_headers,
        )
        assert r_pg.status_code == 200, r_pg.text
        ids = {item["id"] for item in r_pg.json()}
        assert foreign_cred_id not in ids

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
        await dev_client.delete(
            f"/api/v1/gateway/teams/{team.id}/credentials/{cid}", headers=headers
        )

    @pytest.mark.asyncio
    async def test_resync_capabilities_regex_catalog_without_litellm(
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

        def _no_hints(_self, *, provider: str, real_model: str) -> LitellmModelInfoHints | None:
            _ = provider, real_model
            return None

        monkeypatch.setattr(LitellmCapabilityHintAdapter, "get_model_hints", _no_hints)

        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": f"resync-regex-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-resync-regex-test-key-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        model_name = f"resync-regex-{uuid.uuid4().hex[:6]}"
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            json={
                "name": model_name,
                "capability": "chat",
                "real_model": "kimi-k2.6",
                "credential_id": cid,
                "provider": "openai",
                "tags": {},
            },
        )
        assert r_model.status_code == 201, r_model.text
        mid = r_model.json()["id"]

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
        await dev_client.delete(
            f"/api/v1/gateway/teams/{team.id}/credentials/{cid}", headers=headers
        )

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

    @pytest.mark.asyncio
    async def test_dashboard_statistics_pagination_envelope(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        now = datetime.now(UTC)
        cred_ids = [uuid.uuid4() for _ in range(3)]
        db_session.add_all(
            [
                GatewayRequestLog(
                    id=uuid.uuid4(),
                    created_at=now,
                    tenant_id=team.id,
                    user_id=test_user.id,
                    vkey_id=None,
                    credential_id=cred_ids[i],
                    credential_name_snapshot=f"cred-{i}",
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
                    request_id=f"req-stat-{i}",
                )
                for i in range(3)
            ]
        )
        await db_session.commit()

        page_size = 2
        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/dashboard/statistics",
            headers=auth_headers,
            params={
                "group_by": "credential",
                "days": 7,
                "page": 1,
                "page_size": page_size,
            },
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        _assert_paginated_envelope(payload, page=1, page_size=page_size)
        assert payload["total"] == 3
        assert payload["has_next"] is True
        assert payload["has_prev"] is False
        assert len(payload["items"]) == page_size
        assert payload["totals"]["requests"] == 3
        assert payload["group_by"] == "credential"

    @pytest.mark.asyncio
    async def test_dashboard_statistics_provider_filter_query_param(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """``provider`` 查询参数须进入 UsageStatisticsFilters，不得被路径 team_id 覆盖。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        now = datetime.now(UTC)
        db_session.add_all(
            [
                GatewayRequestLog(
                    id=uuid.uuid4(),
                    created_at=now,
                    tenant_id=team.id,
                    user_id=test_user.id,
                    vkey_id=None,
                    credential_id=uuid.uuid4(),
                    capability="chat",
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
                    request_id=f"req-openai-{uuid.uuid4().hex[:8]}",
                ),
                GatewayRequestLog(
                    id=uuid.uuid4(),
                    created_at=now,
                    tenant_id=team.id,
                    user_id=test_user.id,
                    vkey_id=None,
                    credential_id=uuid.uuid4(),
                    capability="chat",
                    real_model="doubao-test",
                    provider="volcengine",
                    status="success",
                    input_tokens=2,
                    output_tokens=2,
                    cached_tokens=0,
                    cost_usd=Decimal("0.002"),
                    latency_ms=12,
                    cache_hit=False,
                    fallback_chain=[],
                    request_id=f"req-volc-{uuid.uuid4().hex[:8]}",
                ),
            ]
        )
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/dashboard/statistics",
            headers=auth_headers,
            params={
                "group_by": "model",
                "days": 7,
                "provider": "volcengine",
                "page": 1,
                "page_size": 20,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["totals"]["requests"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["group_key"] == "doubao-test"

    @pytest.mark.asyncio
    async def test_dashboard_statistics_breakdown_under_user_parent(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        now = datetime.now(UTC)
        cred_a = uuid.uuid4()
        cred_b = uuid.uuid4()
        db_session.add_all(
            [
                GatewayRequestLog(
                    id=uuid.uuid4(),
                    created_at=now,
                    tenant_id=team.id,
                    user_id=test_user.id,
                    vkey_id=None,
                    credential_id=cred_a,
                    credential_name_snapshot="cred-a",
                    capability="chat",
                    route_name="route-a",
                    real_model="gpt-4",
                    provider="openai",
                    status="success",
                    input_tokens=2,
                    output_tokens=1,
                    cached_tokens=0,
                    cost_usd=Decimal("0.002"),
                    latency_ms=10,
                    cache_hit=False,
                    fallback_chain=[],
                    request_id="req-bd-a",
                ),
                GatewayRequestLog(
                    id=uuid.uuid4(),
                    created_at=now,
                    tenant_id=team.id,
                    user_id=test_user.id,
                    vkey_id=None,
                    credential_id=cred_b,
                    credential_name_snapshot="cred-b",
                    capability="chat",
                    route_name="route-b",
                    real_model="gpt-4",
                    provider="openai",
                    status="success",
                    input_tokens=1,
                    output_tokens=1,
                    cached_tokens=0,
                    cost_usd=Decimal("0.001"),
                    latency_ms=12,
                    cache_hit=False,
                    fallback_chain=[],
                    request_id="req-bd-b",
                ),
            ]
        )
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/dashboard/statistics/breakdown",
            headers=auth_headers,
            params={
                "days": 7,
                "parent_group_by": "user",
                "parent_group_key": str(test_user.id),
                "breakdown_by": "credential",
                "top_n": 3,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["parent_requests"] == 2
        assert len(body["items"]) == 2
        shares = sorted(item["share"] for item in body["items"])
        assert shares == pytest.approx([0.5, 0.5])

        bad = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/dashboard/statistics/breakdown",
            headers=auth_headers,
            params={
                "days": 7,
                "parent_group_by": "user",
                "parent_group_key": "not-a-uuid",
                "breakdown_by": "credential",
            },
        )
        assert bad.status_code == 400, bad.text

        bad_breakdown = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/dashboard/statistics/breakdown",
            headers=auth_headers,
            params={
                "days": 7,
                "parent_group_by": "user",
                "parent_group_key": str(test_user.id),
                "breakdown_by": "provider",
            },
        )
        assert bad_breakdown.status_code == 422, bad_breakdown.text

        top32 = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/dashboard/statistics/breakdown",
            headers=auth_headers,
            params={
                "days": 7,
                "parent_group_by": "user",
                "parent_group_key": str(test_user.id),
                "breakdown_by": "credential",
                "top_n": 32,
            },
        )
        assert top32.status_code == 200, top32.text

        over_limit = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/dashboard/statistics/breakdown",
            headers=auth_headers,
            params={
                "days": 7,
                "parent_group_by": "user",
                "parent_group_key": str(test_user.id),
                "breakdown_by": "credential",
                "top_n": 33,
            },
        )
        assert over_limit.status_code == 422, over_limit.text

    @pytest.mark.asyncio
    async def test_dashboard_statistics_breakdown_batch_groups_per_parent(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        now = datetime.now(UTC)
        cred_a = uuid.uuid4()
        cred_b = uuid.uuid4()

        def _log(cred_id: uuid.UUID, cred_name: str, req_suffix: str) -> GatewayRequestLog:
            return GatewayRequestLog(
                id=uuid.uuid4(),
                created_at=now,
                tenant_id=team.id,
                user_id=test_user.id,
                vkey_id=None,
                credential_id=cred_id,
                credential_name_snapshot=cred_name,
                capability="chat",
                route_name="gpt-4",
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
                request_id=f"req-batch-{req_suffix}",
            )

        db_session.add_all(
            [
                _log(cred_a, "cred-a", "a1"),
                _log(cred_a, "cred-a", "a2"),
                _log(cred_b, "cred-b", "b1"),
            ]
        )
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/dashboard/statistics/breakdown-batch",
            headers=auth_headers,
            params={
                "days": 7,
                "parent_group_by": "user",
                "parent_group_keys": [str(test_user.id)],
                "breakdown_by": "credential",
                "top_n": 3,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["parent_group_by"] == "user"
        assert body["breakdown_by"] == "credential"
        assert len(body["items"]) == 1
        parent = body["items"][0]
        assert parent["parent_group_key"] == str(test_user.id)
        assert parent["parent_requests"] == 3
        labels = {item["label"]: item["requests"] for item in parent["items"]}
        assert labels["cred-a"] == 2
        assert labels["cred-b"] == 1
        shares = {item["label"]: item["share"] for item in parent["items"]}
        assert shares["cred-a"] == pytest.approx(2 / 3)

    @pytest.mark.asyncio
    async def test_admin_credential_stats_pagination_envelope(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        db_session,
        admin_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(admin_user.id)
        await db_session.commit()
        page_size = 2
        for i in range(page_size + 1):
            r_cred = await dev_client.post(
                f"/api/v1/gateway/teams/{team.id}/credentials",
                headers=admin_headers,
                json={
                    "provider": "openai",
                    "name": f"plat-stat-{uuid.uuid4().hex[:6]}-{i}",
                    "api_key": "sk-platform-stat-test-key",
                    "scope": "team",
                },
            )
            assert r_cred.status_code == 201, r_cred.text

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/admin/credential-stats",
            headers=admin_headers,
            params={"days": 7, "page": 1, "page_size": page_size},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        _assert_paginated_envelope(payload, page=1, page_size=page_size)
        assert payload["total"] >= page_size + 1
        assert payload["has_next"] is True
        assert len(payload["items"]) == page_size

    @pytest.mark.asyncio
    async def test_models_usage_summary_pagination_and_route_names(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        model_a = f"usage-a-{uuid.uuid4().hex[:6]}"
        model_b = f"usage-b-{uuid.uuid4().hex[:6]}"
        await _create_team_model_via_api(dev_client, team.id, auth_headers, model_name=model_a)
        await _create_team_model_via_api(dev_client, team.id, auth_headers, model_name=model_b)
        now = datetime.now(UTC)
        db_session.add(
            GatewayRequestLog(
                id=uuid.uuid4(),
                created_at=now,
                tenant_id=team.id,
                user_id=test_user.id,
                vkey_id=None,
                capability="chat",
                route_name=model_a,
                real_model="gpt-4o-mini",
                provider="openai",
                status="success",
                input_tokens=5,
                output_tokens=3,
                cached_tokens=0,
                cost_usd=Decimal("0.002"),
                latency_ms=50,
                cache_hit=False,
                fallback_chain=[],
                request_id="req-usage-a",
            )
        )
        await db_session.commit()

        r_page = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models/usage-summary",
            headers=auth_headers,
            params={"days": 7, "page": 1, "page_size": 1},
        )
        assert r_page.status_code == 200, r_page.text
        page_payload = r_page.json()
        _assert_paginated_envelope(page_payload, page=1, page_size=1)
        assert page_payload["total"] >= 2
        assert page_payload["has_next"] is True
        assert "start" in page_payload
        assert "end" in page_payload

        r_scoped = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/models/usage-summary",
            headers=auth_headers,
            params={"days": 7, "route_names": [model_a]},
        )
        assert r_scoped.status_code == 200, r_scoped.text
        scoped_payload = r_scoped.json()
        _assert_paginated_envelope(scoped_payload, page=1, page_size=20)
        assert len(scoped_payload["items"]) == 1
        assert scoped_payload["items"][0]["route_name"] == model_a
        assert scoped_payload["items"][0]["workspace"]["requests"] >= 1


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
        await self._create_team_credential(dev_client, shared.id, auth_headers, name=name_shared)

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
    async def test_list_managed_team_credentials_member_can_read(
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
        await db_session.flush()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(
            name=f"MemberOnly-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await ts.add_member(shared.id, member.id, "member")
        await db_session.flush()

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
        by_name = {item["name"]: item for item in payload["items"]}
        assert owner_cred_name in by_name
        assert by_name[owner_cred_name]["management_access"] == "metadata"
        assert by_name[owner_cred_name]["api_key_masked"] == "—"
        assert by_name[owner_cred_name]["extra"] is None
        assert by_name[owner_cred_name]["effective_api_base_openai"] == "https://api.openai.com/v1"
        assert payload["queried_team_count"] == 1
        assert payload["total"] >= 1

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
        await self._create_team_credential(dev_client, shared.id, auth_headers, name=target_name)

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
            await self._create_team_credential(dev_client, shared.id, auth_headers, name=name)

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
        await self._create_team_model(dev_client, shared.id, auth_headers, model_name=shared_model)

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
        summary = payload["connectivity_summary"]
        assert summary["total"] == summary["success"] + summary["failed"] + summary["unknown"]
        assert summary["total"] >= 1

    @pytest.mark.asyncio
    async def test_managed_team_models_usage_summary_includes_team_id(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """GET /managed-team-models/usage-summary：跨团队聚合且 items 含 team_id。"""
        ts = TeamService(db_session)
        shared = await ts.create_team(
            name=f"UsageAgg-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()

        model_name = f"managed-usage-{uuid.uuid4().hex[:6]}"
        await self._create_team_model(dev_client, shared.id, auth_headers, model_name=model_name)

        now = datetime.now(UTC)
        db_session.add(
            GatewayRequestLog(
                id=uuid.uuid4(),
                created_at=now,
                tenant_id=shared.id,
                user_id=test_user.id,
                vkey_id=None,
                capability="chat",
                route_name=model_name,
                real_model="gpt-4o-mini",
                provider="openai",
                status="success",
                input_tokens=4,
                output_tokens=2,
                cached_tokens=0,
                cost_usd=Decimal("0.001"),
                latency_ms=40,
                cache_hit=False,
                fallback_chain=[],
                request_id="req-managed-usage",
            )
        )
        await db_session.commit()

        r_scoped = await dev_client.get(
            "/api/v1/gateway/managed-team-models/usage-summary",
            headers=auth_headers,
            params={"days": 7, "route_names": [model_name]},
        )
        assert r_scoped.status_code == 200, r_scoped.text
        scoped_payload = r_scoped.json()
        _assert_paginated_envelope(scoped_payload, page=1, page_size=20)
        assert len(scoped_payload["items"]) == 1
        item = scoped_payload["items"][0]
        assert item["route_name"] == model_name
        assert str(item["team_id"]) == str(shared.id)
        assert item["workspace"]["requests"] >= 1

        r_page = await dev_client.get(
            "/api/v1/gateway/managed-team-models/usage-summary",
            headers=auth_headers,
            params={"days": 7, "page": 1, "page_size": 1},
        )
        assert r_page.status_code == 200, r_page.text
        page_payload = r_page.json()
        _assert_paginated_envelope(page_payload, page=1, page_size=1)
        assert page_payload["total"] >= 1
        assert page_payload["has_next"] is True

    @pytest.mark.asyncio
    async def test_list_managed_team_models_member_can_read(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        member = User(
            email=f"managed_model_member_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Managed Model Member",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(
            name=f"MemberModels-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await ts.add_member(shared.id, member.id, "member")
        await db_session.commit()

        owner_model_name = f"owner-model-{uuid.uuid4().hex[:6]}"
        await self._create_team_model(
            dev_client,
            shared.id,
            auth_headers,
            model_name=owner_model_name,
        )

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {"Authorization": f"Bearer {member_token.access_token}"}

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-models",
            headers=member_headers,
            params={"page": 1, "page_size": 50},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        names = {item["name"] for item in payload["items"]}
        assert owner_model_name in names
        assert payload["queried_team_count"] == 1
        assert payload["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_managed_team_models_member_can_filter_by_owner_credential(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """成员无凭据 reveal 权，仍可按团队内模型绑定的 credential_id 筛选聚合列表。"""
        member = User(
            email=f"managed_model_filter_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Managed Model Filter Member",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(
            name=f"FilterCred-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await ts.add_member(shared.id, member.id, "member")
        await db_session.commit()

        owner_model_name = f"owner-filter-{uuid.uuid4().hex[:6]}"
        created = await self._create_team_model(
            dev_client,
            shared.id,
            auth_headers,
            model_name=owner_model_name,
        )
        credential_id = created["credential_id"]

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {"Authorization": f"Bearer {member_token.access_token}"}

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-models",
            headers=member_headers,
            params={
                "page": 1,
                "page_size": 50,
                "credential_id": credential_id,
            },
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["total"] >= 1
        assert all(item["credential_id"] == credential_id for item in payload["items"])
        assert owner_model_name in {item["name"] for item in payload["items"]}

    @pytest.mark.asyncio
    async def test_list_managed_team_model_credential_filters_for_member(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        member = User(
            email=f"managed_cred_filter_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Managed Cred Filter Member",
        )
        db_session.add(member)
        await db_session.flush()
        await db_session.refresh(member)

        ts = TeamService(db_session)
        shared = await ts.create_team(
            name=f"CredFilter-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await ts.add_member(shared.id, member.id, "member")
        await db_session.flush()

        cred_name = f"owner-key-{uuid.uuid4().hex[:6]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": cred_name,
                "api_key": "sk-managed-filter-test-key-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/models",
            headers=auth_headers,
            json={
                "name": f"model-{uuid.uuid4().hex[:6]}",
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cid,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text

        member_uc = UserUseCase(db_session)
        member_token = await member_uc.create_token(member)
        member_headers = {"Authorization": f"Bearer {member_token.access_token}"}

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-model-credential-filters",
            headers=member_headers,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        by_id = {item["id"]: item for item in payload["items"]}
        assert cid in by_id
        assert by_id[cid]["name"] == cred_name
        assert by_id[cid]["tenant_id"] == str(shared.id)

        r_models = await dev_client.get(
            "/api/v1/gateway/managed-team-models",
            headers=member_headers,
            params={"page": 1, "page_size": 50, "credential_id": cid},
        )
        assert r_models.status_code == 200, r_models.text


class TestManagedTeamRoutesAggregateApi:
    async def _create_team_route(
        self,
        dev_client: AsyncClient,
        team_id: uuid.UUID,
        headers: dict[str, str],
        *,
        virtual_model: str,
    ) -> dict[str, object]:
        r = await dev_client.post(
            f"/api/v1/gateway/teams/{team_id}/routes",
            headers=headers,
            json={
                "virtual_model": virtual_model,
                "primary_models": [],
                "strategy": "simple-shuffle",
            },
        )
        assert r.status_code == 201, r.text
        return r.json()

    @pytest.mark.asyncio
    async def test_list_managed_team_routes_includes_personal_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        ts = TeamService(db_session)
        personal = await ts.ensure_personal_team(test_user.id)
        shared = await ts.create_team(
            name=f"RoutesAgg-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()

        personal_virtual = f"personal-route-{uuid.uuid4().hex[:6]}"
        shared_virtual = f"shared-route-{uuid.uuid4().hex[:6]}"
        await self._create_team_route(
            dev_client, personal.id, auth_headers, virtual_model=personal_virtual
        )
        await self._create_team_route(
            dev_client, shared.id, auth_headers, virtual_model=shared_virtual
        )

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-routes",
            headers=auth_headers,
            params={"page": 1, "page_size": 200},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        virtual_models = {item["virtual_model"] for item in payload["items"]}
        assert personal_virtual in virtual_models
        assert shared_virtual in virtual_models
        assert payload["total"] >= 2
        assert payload["page"] == 1
        assert payload["page_size"] == 200
        assert payload["has_next"] is False
        assert payload["has_prev"] is False
        assert payload["queried_personal_team_count"] >= 1
        assert payload["queried_shared_team_count"] >= 1
        assert str(personal.id) in {str(t) for t in payload["tenant_ids_with_routes"]}
        assert str(shared.id) in {str(t) for t in payload["tenant_ids_with_routes"]}


class TestMyRoutesApi:
    @pytest.mark.asyncio
    async def test_my_routes_cross_team_primary(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        ts = TeamService(db_session)
        personal = await ts.ensure_personal_team(test_user.id)
        shared = await ts.create_team(
            name=f"MyRouteCross-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()
        await db_session.refresh(shared)

        shared_model_name = f"shared-primary-{uuid.uuid4().hex[:6]}"
        await _create_team_model_via_api(
            dev_client,
            shared.id,
            auth_headers,
            model_name=shared_model_name,
        )
        route_ref = f"{shared.slug}/{shared_model_name}"
        virtual_model = f"my-virtual-{uuid.uuid4().hex[:6]}"

        r_create = await dev_client.post(
            "/api/v1/gateway/my-routes",
            headers=auth_headers,
            json={
                "virtual_model": virtual_model,
                "primary_models": [route_ref],
                "strategy": "simple-shuffle",
            },
        )
        assert r_create.status_code == 201, r_create.text
        body = r_create.json()
        assert body["virtual_model"] == virtual_model
        assert route_ref in body["primary_models"]

        r_list = await dev_client.get("/api/v1/gateway/my-routes", headers=auth_headers)
        assert r_list.status_code == 200, r_list.text
        virtual_models = {item["virtual_model"] for item in r_list.json()}
        assert virtual_model in virtual_models

        r_callable = await dev_client.get(
            "/api/v1/gateway/my-route-callable-models",
            headers=auth_headers,
            params={"page": 1, "page_size": 200},
        )
        assert r_callable.status_code == 200, r_callable.text
        refs = {item["route_ref"] for item in r_callable.json()["items"]}
        assert route_ref in refs

    @pytest.mark.asyncio
    async def test_my_routes_rejects_unknown_primary(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        r = await dev_client.post(
            "/api/v1/gateway/my-routes",
            headers=auth_headers,
            json={
                "virtual_model": f"bad-route-{uuid.uuid4().hex[:6]}",
                "primary_models": ["unknown-team/ghost-model"],
                "strategy": "simple-shuffle",
            },
        )
        assert r.status_code == 400, r.text
        body = r.json()
        assert body.get("code") == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_my_route_callable_models_pagination_envelope(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        r = await dev_client.get(
            "/api/v1/gateway/my-route-callable-models",
            headers=auth_headers,
            params={"page": 1, "page_size": 10},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert "items" in payload
        assert "total" in payload
        assert payload["page"] == 1
        assert payload["page_size"] == 10
        assert isinstance(payload["has_next"], bool)
        assert isinstance(payload["has_prev"], bool)
        for item in payload["items"]:
            assert "route_ref" in item
            assert "team_kind" in item
            assert "prefix_dispatchable" in item


class TestManagedTeamVirtualKeysAggregateApi:
    @pytest.mark.asyncio
    async def test_list_managed_team_keys_includes_personal_and_shared(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        ts = TeamService(db_session)
        personal = await ts.ensure_personal_team(test_user.id)
        shared = await ts.create_team(
            name=f"KeysAgg-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()

        personal_name = f"personal-key-{uuid.uuid4().hex[:6]}"
        shared_name = f"shared-key-{uuid.uuid4().hex[:6]}"
        r_personal = await dev_client.post(
            f"/api/v1/gateway/teams/{personal.id}/keys",
            headers=auth_headers,
            json={"name": personal_name},
        )
        assert r_personal.status_code == 201, r_personal.text
        r_shared = await dev_client.post(
            f"/api/v1/gateway/teams/{shared.id}/keys",
            headers=auth_headers,
            json={"name": shared_name},
        )
        assert r_shared.status_code == 201, r_shared.text

        r = await dev_client.get(
            "/api/v1/gateway/managed-team-keys",
            headers=auth_headers,
            params={"page": 1, "page_size": 200},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        names = {item["name"] for item in payload["items"]}
        assert personal_name in names
        assert shared_name in names
        assert payload["total"] >= 2
        assert payload["page"] == 1
        assert payload["page_size"] == 200
        assert payload["has_next"] is False
        assert payload["has_prev"] is False
        assert payload["queried_personal_team_count"] >= 1
        assert payload["queried_shared_team_count"] >= 1
        assert str(personal.id) in {str(t) for t in payload["tenant_ids_with_keys"]}
        assert str(shared.id) in {str(t) for t in payload["tenant_ids_with_keys"]}
