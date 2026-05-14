"""Gateway 管理面变更应用服务（CQRS 写侧的工程分包；对外语义见架构文档术语表）。"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bootstrap.config import settings as _settings
from domains.agent.infrastructure.llm.litellm_model_id import build_litellm_model_id
from domains.gateway.domain.errors import (
    CredentialInUseError,
    CredentialNameConflictError,
    CredentialNotFoundError,
    ManagementEntityNotFoundError,
    TeamPermissionDeniedError,
    VirtualKeyNotFoundError,
)
from domains.gateway.infrastructure.repositories.alert_repository import GatewayAlertRepository
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import decrypt_value, derive_encryption_key
from libs.model_connectivity import truncate_last_test_reason
from utils.logging import get_logger

if TYPE_CHECKING:
    from decimal import Decimal
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.alert import GatewayAlertRule


logger = get_logger(__name__)


_TEST_SUPPORTED_CAPABILITIES: frozenset[str] = frozenset({"chat", "embedding"})


class GatewayManagementWriteService:
    """管理 API 状态变更，经仓储与领域服务落库"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._team_svc = TeamService(session)
        self._vkeys = VirtualKeyRepository(session)
        self._creds = ProviderCredentialRepository(session)
        self._models = GatewayModelRepository(session)
        self._routes = GatewayRouteRepository(session)
        self._budgets = BudgetRepository(session)
        self._alerts = GatewayAlertRepository(session)

    async def update_team(
        self,
        team_id: uuid.UUID,
        *,
        name: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> Any | None:
        return await self._team_svc.update_team(team_id, name=name, settings=settings)

    async def delete_shared_team(self, team_id: uuid.UUID) -> None:
        await self._team_svc.delete_shared_team(team_id)

    async def create_virtual_key(
        self,
        *,
        team_id: uuid.UUID,
        created_by_user_id: uuid.UUID | None,
        name: str,
        description: str | None,
        key_id_str: str,
        key_hash: str,
        encrypted_key: str,
        allowed_models: list[str],
        allowed_capabilities: list[str],
        rpm_limit: int | None,
        tpm_limit: int | None,
        store_full_messages: bool,
        guardrail_enabled: bool,
        expires_at: datetime | None,
    ) -> Any:
        return await self._vkeys.create(
            team_id=team_id,
            created_by_user_id=created_by_user_id,
            name=name,
            description=description,
            key_id_str=key_id_str,
            key_hash=key_hash,
            encrypted_key=encrypted_key,
            allowed_models=allowed_models,
            allowed_capabilities=allowed_capabilities,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            store_full_messages=store_full_messages,
            guardrail_enabled=guardrail_enabled,
            expires_at=expires_at,
        )

    async def revoke_virtual_key(
        self,
        key_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
    ) -> None:
        record = await self._vkeys.get(key_id)
        if record is None or record.team_id != team_id:
            raise VirtualKeyNotFoundError(str(key_id))
        if (
            not is_platform_admin
            and team_role == "member"
            and record.created_by_user_id != actor_user_id
        ):
            raise TeamPermissionDeniedError(str(team_id))
        await self._vkeys.revoke(key_id)

    async def create_team_credential(
        self,
        *,
        team_id: uuid.UUID,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None,
        extra: dict[str, Any] | None,
    ) -> Any:
        return await self._creds.create(
            scope="team",
            scope_id=team_id,
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
        )

    async def update_team_credential(
        self,
        credential_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        api_key_encrypted: str | None,
        api_base: str | None,
        extra: dict[str, Any] | None,
        is_active: bool | None,
        name: str | None,
    ) -> Any:
        existing = await self._creds.get(credential_id)
        if existing is None or existing.scope_id != team_id:
            raise CredentialNotFoundError(str(credential_id))
        updated = await self._creds.update(
            credential_id,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
            is_active=is_active,
            name=name,
        )
        if updated is None:
            raise CredentialNotFoundError(str(credential_id))
        return updated

    async def delete_team_credential(self, credential_id: uuid.UUID, *, team_id: uuid.UUID) -> None:
        existing = await self._creds.get(credential_id)
        if existing is None or existing.scope_id != team_id:
            raise CredentialNotFoundError(str(credential_id))
        await self._creds.delete(credential_id)

    async def import_user_credential_to_team(
        self,
        *,
        user_credential_id: uuid.UUID,
        team_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> Any:
        src = await self._creds.get(user_credential_id)
        if src is None or src.scope != "user":
            raise CredentialNotFoundError(str(user_credential_id))
        if src.scope_id != actor_user_id and not is_platform_admin:
            raise TeamPermissionDeniedError(str(team_id))
        new_cred = await self._creds.copy_to_team(user_credential_id, team_id)
        if new_cred is None:
            raise CredentialNotFoundError(str(user_credential_id))
        return new_cred

    async def import_all_user_credentials_to_team(
        self, *, actor_user_id: uuid.UUID, team_id: uuid.UUID
    ) -> int:
        user_creds = await self._creds.list_for_user(actor_user_id)
        created = 0
        for cred in user_creds:
            copied = await self._creds.copy_to_team(cred.id, team_id)
            if copied is not None:
                created += 1
        return created

    async def create_user_credential(
        self,
        *,
        actor_user_id: uuid.UUID,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None,
        extra: dict[str, Any] | None,
    ) -> Any:
        dup = await self._creds.find_user_by_provider_and_name(actor_user_id, provider, name)
        if dup is not None:
            raise CredentialNameConflictError(provider, name)
        return await self._creds.create(
            scope="user",
            scope_id=actor_user_id,
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
        )

    async def update_user_credential(
        self,
        credential_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        api_key_encrypted: str | None,
        api_base: str | None,
        extra: dict[str, Any] | None,
        is_active: bool | None,
        name: str | None,
    ) -> Any:
        existing = await self._creds.get(credential_id)
        if existing is None or existing.scope != "user" or existing.scope_id != actor_user_id:
            raise CredentialNotFoundError(str(credential_id))
        if name is not None and name != existing.name:
            dup = await self._creds.find_user_by_provider_and_name(
                actor_user_id, existing.provider, name
            )
            if dup is not None:
                raise CredentialNameConflictError(existing.provider, name)
        updated = await self._creds.update(
            credential_id,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
            is_active=is_active,
            name=name,
        )
        if updated is None:
            raise CredentialNotFoundError(str(credential_id))
        return updated

    async def delete_user_credential(self, credential_id: uuid.UUID, *, actor_user_id: uuid.UUID) -> None:
        existing = await self._creds.get(credential_id)
        if existing is None or existing.scope != "user" or existing.scope_id != actor_user_id:
            raise CredentialNotFoundError(str(credential_id))
        in_use = await self._models.count_by_credential_id(credential_id)
        if in_use > 0:
            raise CredentialInUseError(str(credential_id))
        await self._creds.delete(credential_id)

    async def sync_user_provider_legacy_row(
        self,
        *,
        actor_user_id: uuid.UUID,
        provider: str,
        api_key_encrypted: str,
        api_base: str | None,
        is_active: bool,
    ) -> Any:
        """与旧版单条 UserProviderConfig 双写：更新或创建 user scope 凭据（优先 name=default）。"""
        rows = await self._creds.list_user_by_provider(actor_user_id, provider)
        target: Any | None = None
        for row in rows:
            if row.name == "default":
                target = row
                break
        if target is None:
            for row in rows:
                if row.name == provider:
                    target = row
                    break
        if target is None and len(rows) == 1:
            target = rows[0]
        if target is not None:
            updated = await self._creds.update(
                target.id,
                api_key_encrypted=api_key_encrypted,
                api_base=api_base,
                extra=None,
                is_active=is_active,
                name=None,
            )
            if updated is None:
                raise CredentialNotFoundError(str(target.id))
            return updated
        return await self._creds.create(
            scope="user",
            scope_id=actor_user_id,
            provider=provider,
            name="default",
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=None,
            is_active=is_active,
        )

    async def delete_all_user_credentials_for_provider(
        self, *, actor_user_id: uuid.UUID, provider: str
    ) -> None:
        rows = await self._creds.list_user_by_provider(actor_user_id, provider)
        for row in rows:
            await self.delete_user_credential(row.id, actor_user_id=actor_user_id)

    async def create_gateway_model(
        self,
        *,
        team_id: uuid.UUID,
        name: str,
        capability: str,
        real_model: str,
        credential_id: uuid.UUID,
        provider: str,
        weight: int,
        rpm_limit: int | None,
        tpm_limit: int | None,
        tags: dict[str, Any] | None,
    ) -> Any:
        return await self._models.create(
            team_id=team_id,
            name=name,
            capability=capability,
            real_model=real_model,
            credential_id=credential_id,
            provider=provider,
            weight=weight,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            tags=tags,
        )

    async def update_gateway_model(
        self,
        model_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> Any:
        repo = self._models
        existing = await repo.get(model_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise ManagementEntityNotFoundError("model", str(model_id))
        updated = await repo.update(model_id, **fields)
        if updated is None:
            raise ManagementEntityNotFoundError("model", str(model_id))
        return updated

    async def delete_gateway_model(self, model_id: uuid.UUID, *, team_id: uuid.UUID) -> None:
        repo = self._models
        existing = await repo.get(model_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise CredentialNotFoundError(str(model_id))
        await repo.delete(model_id)

    async def test_gateway_model(
        self,
        model_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
    ) -> dict[str, Any]:
        """对 Gateway 团队模型发起一次最小 LLM 调用做连通性测试。

        - 仅支持 ``capability ∈ {chat, embedding}``；其它返回 ``success=false``
          + ``status=failed`` 并写回字段，避免前端误以为"未测过"。
        - 直连 ``litellm.acompletion`` / ``litellm.aembedding`` 并显式传入
          解密后的 ``api_key`` 与 ``api_base``，绕过 Gateway 内部桥接，确保探
          测的就是这条记录本身的凭据。
        无论成功/失败，均把 ``last_test_status`` + ``last_tested_at`` +
        ``last_test_reason`` 写回 ``gateway_models``，列表页可直接展示连通状态。
        """
        existing = await self._models.get(model_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise ManagementEntityNotFoundError("model", str(model_id))

        capability = existing.capability
        litellm_model = build_litellm_model_id(existing.provider, existing.real_model)
        tested_at = datetime.now(UTC)

        if capability not in _TEST_SUPPORTED_CAPABILITIES:
            msg = f"capability={capability} 暂不支持连通性测试"
            reason = truncate_last_test_reason(msg)
            await self._models.update(
                model_id,
                last_test_status="failed",
                last_tested_at=tested_at,
                last_test_reason=reason,
            )
            return {
                "success": False,
                "message": msg,
                "model": litellm_model,
                "status": "failed",
                "tested_at": tested_at,
                "reason": reason,
            }

        credential = await self._creds.get(existing.credential_id)
        if credential is None:
            msg = "关联凭据已不存在"
            reason = truncate_last_test_reason(msg)
            await self._models.update(
                model_id,
                last_test_status="failed",
                last_tested_at=tested_at,
                last_test_reason=reason,
            )
            return {
                "success": False,
                "message": msg,
                "model": litellm_model,
                "status": "failed",
                "tested_at": tested_at,
                "reason": reason,
            }

        encryption_key = derive_encryption_key(_settings.secret_key.get_secret_value())
        try:
            api_key = decrypt_value(credential.api_key_encrypted, encryption_key)
        except Exception as exc:  # pragma: no cover - 极端配置异常
            logger.warning("Failed to decrypt credential %s: %s", credential.id, exc)
            msg = f"凭据解密失败: {exc}"
            reason = truncate_last_test_reason(msg)
            await self._models.update(
                model_id,
                last_test_status="failed",
                last_tested_at=tested_at,
                last_test_reason=reason,
            )
            return {
                "success": False,
                "message": msg,
                "model": litellm_model,
                "status": "failed",
                "tested_at": tested_at,
                "reason": reason,
            }

        api_base = credential.api_base
        # 延迟导入 litellm，避免在模块加载阶段拉起重型依赖。
        from litellm import (  # pylint: disable=import-error,import-outside-toplevel
            acompletion,
            aembedding,
        )

        try:
            if capability == "chat":
                response = await acompletion(
                    model=litellm_model,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=10,
                    temperature=0,
                    api_key=api_key,
                    api_base=api_base,
                )
                preview = ""
                with suppress(Exception):
                    preview = (response.choices[0].message.content or "")[:100]
                await self._models.update(
                    model_id,
                    last_test_status="success",
                    last_tested_at=tested_at,
                    last_test_reason=None,
                )
                return {
                    "success": True,
                    "message": "连接成功",
                    "model": litellm_model,
                    "status": "success",
                    "tested_at": tested_at,
                    "reason": None,
                    "response_preview": preview,
                }

            await aembedding(
                model=litellm_model,
                input=["ping"],
                api_key=api_key,
                api_base=api_base,
            )
            await self._models.update(
                model_id,
                last_test_status="success",
                last_tested_at=tested_at,
                last_test_reason=None,
            )
            return {
                "success": True,
                "message": "连接成功",
                "model": litellm_model,
                "status": "success",
                "tested_at": tested_at,
                "reason": None,
            }
        except Exception as exc:
            logger.warning("Gateway model %s connection test failed: %s", model_id, exc)
            msg = f"连接失败: {exc}"
            reason = truncate_last_test_reason(msg)
            await self._models.update(
                model_id,
                last_test_status="failed",
                last_tested_at=tested_at,
                last_test_reason=reason,
            )
            return {
                "success": False,
                "message": msg,
                "model": litellm_model,
                "status": "failed",
                "tested_at": tested_at,
                "reason": reason,
            }

    async def create_gateway_route(
        self,
        *,
        team_id: uuid.UUID,
        virtual_model: str,
        primary_models: list[str],
        fallbacks_general: list[str],
        fallbacks_content_policy: list[str],
        fallbacks_context_window: list[str],
        strategy: str,
        retry_policy: dict[str, Any],
    ) -> Any:
        return await self._routes.create(
            team_id=team_id,
            virtual_model=virtual_model,
            primary_models=primary_models,
            fallbacks_general=fallbacks_general,
            fallbacks_content_policy=fallbacks_content_policy,
            fallbacks_context_window=fallbacks_context_window,
            strategy=strategy,
            retry_policy=retry_policy,
        )

    async def update_gateway_route(
        self,
        route_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> Any:
        repo = self._routes
        existing = await repo.get(route_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise ManagementEntityNotFoundError("route", str(route_id))
        updated = await repo.update(route_id, **fields)
        if updated is None:
            raise ManagementEntityNotFoundError("route", str(route_id))
        return updated

    async def delete_gateway_route(self, route_id: uuid.UUID, *, team_id: uuid.UUID) -> None:
        repo = self._routes
        existing = await repo.get(route_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise ManagementEntityNotFoundError("route", str(route_id))
        await repo.delete(route_id)

    async def reload_litellm_router(self) -> None:
        from domains.gateway.infrastructure.router_singleton import reload_router

        with suppress(Exception):  # pragma: no cover
            await reload_router(self._session)

    async def upsert_budget(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID | None,
        period: str,
        model_name: str | None = None,
        limit_usd: Decimal | None,
        limit_tokens: int | None,
        limit_requests: int | None,
    ) -> Any:
        return await self._budgets.upsert(
            scope=scope,
            scope_id=scope_id,
            period=period,
            model_name=model_name,
            limit_usd=limit_usd,
            limit_tokens=limit_tokens,
            limit_requests=limit_requests,
        )

    async def delete_budget(self, budget_id: uuid.UUID) -> None:
        await self._budgets.delete(budget_id)

    async def create_alert_rule(
        self,
        *,
        team_id: uuid.UUID,
        name: str,
        description: str | None,
        metric: str,
        threshold: Decimal,
        window_minutes: int,
        channels: dict[str, Any],
        enabled: bool,
    ) -> GatewayAlertRule:
        return await self._alerts.create_rule(
            team_id=team_id,
            name=name,
            description=description,
            metric=metric,
            threshold=threshold,
            window_minutes=window_minutes,
            channels=channels,
            enabled=enabled,
        )

    async def update_alert_rule(
        self,
        rule_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> GatewayAlertRule:
        rule = await self._alerts.get_rule(rule_id)
        if rule is None or rule.team_id != team_id:
            raise ManagementEntityNotFoundError("alert_rule", str(rule_id))
        return await self._alerts.update_rule_fields(rule, fields)

    async def delete_alert_rule(self, rule_id: uuid.UUID, *, team_id: uuid.UUID) -> None:
        rule = await self._alerts.get_rule(rule_id)
        if rule is None or rule.team_id != team_id:
            raise ManagementEntityNotFoundError("alert_rule", str(rule_id))
        await self._alerts.delete_rule(rule)


__all__ = ["GatewayManagementWriteService"]
