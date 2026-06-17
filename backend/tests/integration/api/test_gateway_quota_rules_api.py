"""
Gateway 配额规则统一 API 集成测试。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService


@pytest.mark.integration
class TestGatewayQuotaRulesApi:
    @pytest.mark.asyncio
    async def test_list_quota_rules_includes_platform_budget(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        budget = GatewayBudget(
            target_kind="tenant",
            target_id=team.id,
            period="monthly",
            model_name=None,
            limit_usd=Decimal("50"),
        )
        db_session.add(budget)
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/quota-rules",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        assert any(
            row["key"]["layer"] == "platform" and row["source_ref"]["budget_id"] is not None
            for row in rows
        )

    @pytest.mark.asyncio
    async def test_batch_upsert_platform_quota(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        r = await dev_client.put(
            f"/api/v1/gateway/teams/{team.id}/quota-rules/batch",
            headers=auth_headers,
            json={
                "rules": [
                    {
                        "layer": "platform",
                        "target_kind": "tenant",
                        "period": "daily",
                        "limit_usd": "25.00",
                    }
                ]
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["succeeded"]) == 1
        assert body["failed"] == []

        listed = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/quota-rules?layer=platform",
            headers=auth_headers,
        )
        assert listed.status_code == 200
        assert any(row["key"]["period"] == "daily" for row in listed.json())

    @pytest.mark.asyncio
    async def test_batch_upsert_platform_daily_custom_anchor_fields(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        r = await dev_client.put(
            f"/api/v1/gateway/teams/{team.id}/quota-rules/batch",
            headers=auth_headers,
            json={
                "rules": [
                    {
                        "layer": "platform",
                        "target_kind": "tenant",
                        "period": "daily",
                        "limit_usd": "10.00",
                        "period_timezone": "Asia/Shanghai",
                        "period_reset_minutes": 540,
                    }
                ]
            },
        )
        assert r.status_code == 200, r.text
        listed = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/quota-rules?layer=platform&include_usage=true",
            headers=auth_headers,
        )
        assert listed.status_code == 200
        rows = listed.json()
        row = next(r for r in rows if r["key"]["period"] == "daily")
        assert row["key"]["period_timezone"] == "Asia/Shanghai"
        assert row["key"]["period_reset_minutes"] == 540
        assert row["usage"] is not None
        assert row["usage"]["window_start"] is not None
        assert row["usage"]["reset_at"] is not None

    @pytest.mark.asyncio
    async def test_batch_upsert_upstream_quota_appears_in_list(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """配额中心 upstream batch 写入后，list（含 include_usage）应可见。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()

        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"quota-upstream-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-quota-upstream-test-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        credential_id = r_cred.json()["id"]
        real_model = "openai/gpt-4o-mini"

        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=auth_headers,
            json={
                "name": f"quota-upstream-model-{uuid.uuid4().hex[:8]}",
                "capability": "chat",
                "real_model": real_model,
                "credential_id": credential_id,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text

        r_batch = await dev_client.put(
            f"/api/v1/gateway/teams/{team.id}/quota-rules/batch",
            headers=auth_headers,
            json={
                "rules": [
                    {
                        "layer": "upstream",
                        "credential_id": credential_id,
                        "model_name": real_model,
                        "window_seconds": 0,
                        "quota_label": "default",
                        "limit_usd": "10.00",
                    }
                ]
            },
        )
        assert r_batch.status_code == 200, r_batch.text
        batch_body = r_batch.json()
        assert batch_body["failed"] == [], batch_body
        assert len(batch_body["succeeded"]) == 1, batch_body

        r_list = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/quota-rules",
            headers=auth_headers,
            params={"layer": "upstream", "include_usage": "true"},
        )
        assert r_list.status_code == 200, r_list.text
        rows = r_list.json()
        assert any(
            row["key"]["layer"] == "upstream"
            and row["key"]["credential_id"] == credential_id
            and row["limits"]["limit_usd"] is not None
            and float(row["limits"]["limit_usd"]) == 10.0
            for row in rows
        ), rows

    @pytest.mark.asyncio
    async def test_batch_upsert_upstream_rejects_unregistered_real_model(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """上游配额：凭据下未注册的 real_model 应 batch 失败。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()

        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"quota-upstream-bad-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-quota-upstream-bad-test-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        credential_id = r_cred.json()["id"]

        r_batch = await dev_client.put(
            f"/api/v1/gateway/teams/{team.id}/quota-rules/batch",
            headers=auth_headers,
            json={
                "rules": [
                    {
                        "layer": "upstream",
                        "credential_id": credential_id,
                        "model_name": "openai/gpt-4o-mini",
                        "window_seconds": 0,
                        "quota_label": "default",
                        "limit_usd": "10.00",
                    }
                ]
            },
        )
        assert r_batch.status_code == 200, r_batch.text
        batch_body = r_batch.json()
        assert batch_body["succeeded"] == [], batch_body
        assert len(batch_body["failed"]) == 1, batch_body
        assert "未注册在该凭据下" in batch_body["failed"][0]["error"]

    @pytest.mark.asyncio
    async def test_provider_plan_api_rejects_unregistered_real_model(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """凭据页创建 ProviderPlan 也须 real_model 已在凭据注册。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        now = datetime.now(UTC).replace(microsecond=0)

        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"quota-plan-bad-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-quota-plan-bad-test-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        credential_id = r_cred.json()["id"]

        r_plan = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials/{credential_id}/provider-plans",
            headers=auth_headers,
            json={
                "real_model": "openai/gpt-4o-mini",
                "label": "pack",
                "valid_from": (now - timedelta(minutes=1)).isoformat(),
                "valid_until": (now + timedelta(days=30)).isoformat(),
                "quotas": [
                    {
                        "label": "daily",
                        "window_seconds": 86400,
                        "reset_strategy": "calendar_daily_utc",
                        "limit_requests": 50,
                    }
                ],
            },
        )
        assert r_plan.status_code == 400, r_plan.text
        body = r_plan.json()
        assert body.get("code") == "VALIDATION_ERROR", body
        assert "未注册在该凭据下" in body.get("detail", "")

    @pytest.mark.asyncio
    async def test_provider_plan_via_credential_api_appears_in_quota_list(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """凭据页创建的 ProviderPlan 配额也应在配额中心 upstream 列表出现。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        now = datetime.now(UTC).replace(microsecond=0)

        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"quota-plan-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-quota-plan-test-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        credential_id = r_cred.json()["id"]

        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=auth_headers,
            json={
                "name": f"quota-plan-model-{uuid.uuid4().hex[:8]}",
                "capability": "chat",
                "real_model": "openai/gpt-4o-mini",
                "credential_id": credential_id,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text

        r_plan = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials/{credential_id}/provider-plans",
            headers=auth_headers,
            json={
                "real_model": "openai/gpt-4o-mini",
                "label": "pack",
                "valid_from": (now - timedelta(minutes=1)).isoformat(),
                "valid_until": (now + timedelta(days=30)).isoformat(),
                "quotas": [
                    {
                        "label": "daily",
                        "window_seconds": 86400,
                        "reset_strategy": "calendar_daily_utc",
                        "limit_requests": 50,
                    }
                ],
            },
        )
        assert r_plan.status_code == 201, r_plan.text

        r_list = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/quota-rules",
            headers=auth_headers,
            params={"layer": "upstream", "include_usage": "true"},
        )
        assert r_list.status_code == 200, r_list.text
        rows = r_list.json()
        assert any(
            row["key"]["credential_id"] == credential_id and row["key"]["quota_label"] == "daily"
            for row in rows
        ), rows

    @pytest.mark.asyncio
    async def test_self_batch_personal_byok_upstream_appears_in_list(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """成员自助：本人 BYOK upstream 写入后应在个人工作区配额列表可见。"""
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()

        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"quota-byok-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-quota-byok-upstream-test-key-123",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        credential_id = r_cred.json()["id"]
        real_model = "gpt-4o-mini"

        r_model = await dev_client.post(
            "/api/v1/gateway/my-models",
            headers=auth_headers,
            json={
                "display_name": "Quota BYOK Model",
                "provider": "openai",
                "model_id": real_model,
                "credential_id": credential_id,
                "model_types": ["text"],
            },
        )
        assert r_model.status_code == 201, r_model.text

        r_batch = await dev_client.put(
            f"/api/v1/gateway/teams/{team.id}/quota-rules/self-batch",
            headers=auth_headers,
            json={
                "rules": [
                    {
                        "layer": "upstream",
                        "credential_id": credential_id,
                        "model_name": real_model,
                        "window_seconds": 0,
                        "quota_label": "default",
                        "limit_usd": "5.00",
                    }
                ]
            },
        )
        assert r_batch.status_code == 200, r_batch.text
        batch_body = r_batch.json()
        assert batch_body["failed"] == [], batch_body
        assert len(batch_body["succeeded"]) == 1, batch_body
        assert batch_body["succeeded"][0]["key"]["team_id"] == str(team.id)

        r_list = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/quota-rules",
            headers=auth_headers,
            params={
                "layer": "upstream",
                "credential_id": credential_id,
                "include_usage": "true",
            },
        )
        assert r_list.status_code == 200, r_list.text
        rows = r_list.json()
        assert any(
            row["key"]["layer"] == "upstream"
            and row["key"]["credential_id"] == credential_id
            and float(row["limits"]["limit_usd"]) == 5.0
            for row in rows
        ), rows

    @pytest.mark.asyncio
    async def test_adjust_platform_quota_usage(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        r_batch = await dev_client.put(
            f"/api/v1/gateway/teams/{team.id}/quota-rules/batch",
            headers=auth_headers,
            json={
                "rules": [
                    {
                        "layer": "platform",
                        "target_kind": "tenant",
                        "period": "daily",
                        "limit_usd": "100.00",
                    }
                ]
            },
        )
        assert r_batch.status_code == 200, r_batch.text
        budget_id = r_batch.json()["succeeded"][0]["source_ref"]["budget_id"]

        r_adj = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/quota-rules/usage-adjustments",
            headers=auth_headers,
            json={
                "layer": "platform",
                "budget_id": budget_id,
                "mode": "set",
                "current_usd": "12.50",
                "current_tokens": 1000,
                "current_requests": 3,
            },
        )
        assert r_adj.status_code == 200, r_adj.text
        body = r_adj.json()
        assert body["usage"] is not None
        assert float(body["usage"]["current_usd"]) == 12.5
        assert body["usage"]["current_tokens"] == 1000
        assert body["usage"]["current_requests"] == 3

    @pytest.mark.asyncio
    async def test_adjust_upstream_quota_usage(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()

        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"quota-adj-up-{uuid.uuid4().hex[:8]}",
                "api_key": "sk-quota-adj-upstream-test-123456789",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        credential_id = r_cred.json()["id"]
        real_model = "openai/gpt-4o-mini"

        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=auth_headers,
            json={
                "name": f"quota-adj-model-{uuid.uuid4().hex[:8]}",
                "capability": "chat",
                "real_model": real_model,
                "credential_id": credential_id,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text

        r_batch = await dev_client.put(
            f"/api/v1/gateway/teams/{team.id}/quota-rules/batch",
            headers=auth_headers,
            json={
                "rules": [
                    {
                        "layer": "upstream",
                        "credential_id": credential_id,
                        "model_name": real_model,
                        "window_seconds": 0,
                        "quota_label": "default",
                        "limit_usd": "20.00",
                        "limit_requests": 3,
                    }
                ]
            },
        )
        assert r_batch.status_code == 200, r_batch.text
        rule = r_batch.json()["succeeded"][0]

        r_adj = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/quota-rules/usage-adjustments",
            headers=auth_headers,
            json={
                "layer": "upstream",
                "plan_id": rule["source_ref"]["plan_id"],
                "quota_id": rule["source_ref"]["quota_id"],
                "mode": "set",
                "current_usd": "3.25",
                "current_tokens": 500,
                "current_requests": 2,
            },
        )
        assert r_adj.status_code == 200, r_adj.text
        body = r_adj.json()
        assert body["usage"] is not None
        assert float(body["usage"]["current_usd"]) == 3.25
        assert body["usage"]["current_tokens"] == 500
        assert body["usage"]["current_requests"] == 2

        from domains.gateway.application.management.plan_read_mappers import (
            provider_plan_quota_to_spec,
        )
        from domains.gateway.application.quota_plan_service import get_quota_plan_service
        from domains.gateway.domain.quota_plan import PROVIDER_NS
        from domains.gateway.infrastructure.repositories.provider_plan_repository import (
            ProviderPlanRepository,
        )

        plan_uuid = uuid.UUID(rule["source_ref"]["plan_id"])
        quota_uuid = uuid.UUID(rule["source_ref"]["quota_id"])
        loaded = await ProviderPlanRepository(db_session).get_with_quotas(plan_uuid)
        assert loaded is not None
        plan, quotas = loaded
        quota_row = next(q for q in quotas if q.id == quota_uuid)
        spec = provider_plan_quota_to_spec(quota_row, plan_valid_from=plan.valid_from)
        snap = (await get_quota_plan_service().snapshot(PROVIDER_NS, plan_uuid, [spec]))[0]
        assert snap.used_usd == Decimal("3.25")
        assert snap.used_tokens == 500
        assert snap.used_requests == 2

        allowed = await get_quota_plan_service().check_and_reserve(
            PROVIDER_NS,
            plan_uuid,
            [spec],
            request_count=1,
        )
        assert allowed.allowed
        blocked = await get_quota_plan_service().check_and_reserve(
            PROVIDER_NS,
            plan_uuid,
            [spec],
            request_count=1,
        )
        assert not blocked.allowed
        assert blocked.exhausted_snapshot is not None
        assert blocked.exhausted_snapshot.exhausted_reason == "requests"

    @pytest.mark.asyncio
    async def test_adjust_usage_rejects_cross_team_budget(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team_a = await TeamService(db_session).ensure_personal_team(test_user.id)
        team_b = await TeamService(db_session).create_team(
            name="quota-adj-other",
            slug=f"quota-adj-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()

        r_batch = await dev_client.put(
            f"/api/v1/gateway/teams/{team_a.id}/quota-rules/batch",
            headers=auth_headers,
            json={
                "rules": [
                    {
                        "layer": "platform",
                        "target_kind": "tenant",
                        "period": "daily",
                        "limit_usd": "50.00",
                    }
                ]
            },
        )
        assert r_batch.status_code == 200, r_batch.text
        budget_id = r_batch.json()["succeeded"][0]["source_ref"]["budget_id"]

        r_adj = await dev_client.post(
            f"/api/v1/gateway/teams/{team_b.id}/quota-rules/usage-adjustments",
            headers=auth_headers,
            json={
                "layer": "platform",
                "budget_id": budget_id,
                "mode": "set",
                "current_usd": "1.00",
                "current_tokens": 1,
                "current_requests": 1,
            },
        )
        assert r_adj.status_code == 404, r_adj.text
