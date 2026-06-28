"""Gateway 管理面：模型连通性探活。"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from typing import Any
import uuid

from bootstrap.config import settings as _settings
from domains.gateway.application.catalog.management.model_test_constants import (
    GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES,
    VIDEO_PROBE_TIMEOUT,
)
from domains.gateway.application.catalog.management.probe_image_preview import (
    image_generation_probe_preview,
)
from domains.gateway.application.catalog.management.probe_litellm_attribution import (
    merge_probe_litellm_kwargs,
)
from domains.gateway.application.catalog.management.probe_recording import (
    record_gateway_model_test_failure,
    record_gateway_model_test_success,
)
from domains.gateway.application.catalog.management.probe_target import (
    EncryptedCredentialSnapshot,
    ProbeCredentialSnapshot,
    ProbeTarget,
)
from domains.gateway.application.catalog.management.probe_video_preview import (
    video_generation_probe_preview,
)
from domains.gateway.application.route.router_deployment_params import (
    VOLCENGINE_IMAGE_ENDPOINT_PROBE_MESSAGE,
    require_volcengine_image_endpoint_id,
)
from domains.gateway.domain.errors import ManagementEntityNotFoundError
from domains.gateway.domain.litellm.litellm_model_id import resolve_probe_litellm_model
from domains.gateway.domain.provider.agnes_image import (
    build_agnes_image_probe_request,
    should_use_agnes_direct_image,
)
from domains.gateway.domain.provider.dashscope_embedding import (
    build_dashscope_embedding_request,
    should_use_dashscope_direct_embedding,
)
from domains.gateway.domain.provider.provider_env_catalog import image_probe_size
from domains.gateway.domain.provider.volcengine_image import build_volcengine_image_probe_request
from domains.gateway.domain.provider.volcengine_video import (
    build_volcengine_video_create_request,
    map_volcengine_video_task_to_openai,
    should_use_volcengine_direct_video,
)
from domains.gateway.domain.proxy.temperature_policy import resolve_probe_chat_temperature
from domains.gateway.infrastructure.litellm.router_singleton import ensure_gateway_callbacks
from domains.gateway.infrastructure.upstream.agnes_image_client import (
    perform_agnes_image_generation,
)
from domains.gateway.infrastructure.upstream.dashscope_embedding_client import (
    perform_dashscope_embedding,
)
from domains.gateway.infrastructure.upstream.volcengine_image_client import (
    perform_volcengine_image_generation,
)
from domains.gateway.infrastructure.upstream.volcengine_video_client import (
    perform_volcengine_video_create,
)
from domains.identity.application.user_display import resolve_user_display_snapshot
from libs.crypto import decrypt_value, derive_encryption_key
from libs.exceptions import PermissionDeniedError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)


class ProbeWritesMixin:
    """模型连通性探活。"""

    async def test_personal_model(self, user_id: uuid.UUID, model_id: uuid.UUID) -> dict[str, Any]:
        tenant_id = await self._ensure_personal_tenant_id(user_id)
        return await self.test_gateway_model(
            model_id,
            tenant_id=tenant_id,
            actor_user_id=user_id,
        )

    async def _resolve_probe_target(
        self,
        model_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
    ) -> ProbeTarget:
        tenant_row = await self._models.get(model_id)
        if tenant_row is not None:
            if tenant_row.tenant_id is not None and tenant_row.tenant_id != tenant_id:
                raise ManagementEntityNotFoundError("model", str(model_id))
            return ProbeTarget(
                model_id=model_id,
                capability=tenant_row.capability,
                provider=tenant_row.provider,
                real_model=tenant_row.real_model,
                credential_id=tenant_row.credential_id,
                is_system=False,
                model_name=tenant_row.name,
            )
        system_row = await self._models.get_system(model_id)
        if system_row is None:
            raise ManagementEntityNotFoundError("model", str(model_id))
        return ProbeTarget(
            model_id=model_id,
            capability=system_row.capability,
            provider=system_row.provider,
            real_model=system_row.real_model,
            credential_id=system_row.credential_id,
            is_system=True,
            model_name=system_row.name,
        )

    async def _load_probe_credential(
        self,
        target: ProbeTarget,
    ) -> EncryptedCredentialSnapshot | None:
        if target.is_system:
            return await self._system_creds.get(target.credential_id)
        return await self._creds.get(target.credential_id)

    async def _resolve_probe_actor_user_id(
        self,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if actor_user_id is not None:
            return actor_user_id
        team = await self._teams.get_team(tenant_id)
        if team is not None and team.kind == "personal":
            return team.owner_user_id
        return None

    async def test_gateway_model(
        self,
        model_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
        team_role: str = "member",
        is_platform_admin: bool = False,
    ) -> dict[str, Any]:
        target = await self._resolve_probe_target(model_id, tenant_id=tenant_id)
        # system 模型使用平台级 system 凭据，没有 tenant 凭据上下文，
        # 因此不能复用针对 tenant 凭据的 _assert_team_model_mutation_allowed。
        if target.is_system and not is_platform_admin:
            raise PermissionDeniedError("system model probe requires platform admin")
        if not target.is_system:
            # 探活会消耗上游 API 额度并产生真实请求，视为对凭据的「写副作用」；
            # 因此复用 update 权限策略，确保只有凭据 owner / team_admin / platform_admin 可执行。
            await self._assert_team_model_mutation_allowed(
                credential_id=target.credential_id,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
                mutation="update",
            )
        capability = target.capability
        tested_at = datetime.now(UTC)
        record_kw = {"is_system": target.is_system}
        litellm_model = target.real_model
        if capability not in GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES:
            msg = f"capability={capability} 暂不支持连通性测试"
            return await record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model, **record_kw
            )
        credential = await self._load_probe_credential(target)
        if credential is None:
            msg = "关联凭据已不存在"
            return await record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model, **record_kw
            )
        encryption_key = derive_encryption_key(_settings.secret_key.get_secret_value())
        try:
            api_key = decrypt_value(credential.api_key_encrypted, encryption_key)
        except Exception as exc:
            logger.warning("Failed to decrypt credential %s: %s", credential.id, exc)
            msg = f"凭据解密失败: {exc}"
            return await record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model, **record_kw
            )
        cred = ProbeCredentialSnapshot.from_encrypted(credential, api_key=api_key)
        # 探活直连 litellm 顶层 ``a*`` 函数（非 Router），provider 只能从 model 串推断；
        # ``aimage_generation`` / ``avideo_generation`` 不接受 ``custom_llm_provider`` kwarg。
        # 因此须带 ``provider/`` 前缀（OpenAI-compat 自定义端点 / 第三方伪兼容 → ``openai/<id>``），
        # 而非 Router 出站用的裸 ``real_model``（其 provider 靠 litellm_params 携带）。
        litellm_model = resolve_probe_litellm_model(
            target.provider, target.real_model, api_base=cred.api_base
        )
        probe_chat_temperature = (
            resolve_probe_chat_temperature(
                credential_profile_id=cred.profile_id,
                provider=target.provider,
            )
            if capability == "chat"
            else None
        )
        probe_actor_id = await self._resolve_probe_actor_user_id(tenant_id, actor_user_id)
        probe_user_snapshot = await resolve_user_display_snapshot(self._session, probe_actor_id)
        ensure_gateway_callbacks()
        from libs.db.session_lifecycle import release_session_before_blocking_io

        await release_session_before_blocking_io(self._session)
        from litellm import acompletion, aembedding, aimage_generation, avideo_generation

        def _litellm_kw(base: dict[str, Any]) -> dict[str, Any]:
            return merge_probe_litellm_kwargs(
                base,
                tenant_id=tenant_id,
                actor_user_id=probe_actor_id,
                target=target,
                credential_name=cred.name,
                user_email_snapshot=probe_user_snapshot,
                credential_profile_id=cred.profile_id,
            )

        try:
            if capability == "chat":
                response = await acompletion(
                    **_litellm_kw(
                        {
                            "model": litellm_model,
                            "messages": [{"role": "user", "content": "Hi"}],
                            "max_tokens": 10,
                            "temperature": probe_chat_temperature,
                            "api_key": cred.api_key,
                            "api_base": cred.api_base,
                        }
                    )
                )
                preview = ""
                with suppress(Exception):
                    preview = (response.choices[0].message.content or "")[:100]
                return await record_gateway_model_test_success(
                    self._models,
                    model_id,
                    tested_at,
                    litellm_model,
                    response_preview=preview,
                    **record_kw,
                )
            if capability == "image":
                img_size = image_probe_size(target.provider)
                if should_use_agnes_direct_image(target.provider):
                    agnes_request = build_agnes_image_probe_request(
                        api_key=cred.api_key,
                        api_base=cred.api_base,
                        model=target.real_model,
                        profile_id=cred.profile_id,
                        size=img_size,
                    )
                    img_data = await perform_agnes_image_generation(agnes_request)
                    preview = image_generation_probe_preview(img_data)
                elif target.provider == "volcengine":
                    try:
                        image_endpoint_id = require_volcengine_image_endpoint_id(
                            cred.extra,
                            message=VOLCENGINE_IMAGE_ENDPOINT_PROBE_MESSAGE,
                        )
                    except ValidationError as exc:
                        return await record_gateway_model_test_failure(
                            self._models,
                            model_id,
                            tested_at,
                            str(exc),
                            litellm_model,
                            **record_kw,
                        )
                    request = build_volcengine_image_probe_request(
                        api_key=cred.api_key,
                        api_base=cred.api_base,
                        image_endpoint_id=image_endpoint_id,
                        profile_id=cred.profile_id,
                        size=img_size,
                    )
                    img_data = await perform_volcengine_image_generation(request)
                    preview = image_generation_probe_preview(img_data)
                else:
                    img_response = await aimage_generation(
                        **_litellm_kw(
                            {
                                "model": litellm_model,
                                "prompt": "ping",
                                "n": 1,
                                "size": img_size,
                                "api_key": cred.api_key,
                                "api_base": cred.api_base,
                                "timeout": 60,
                            }
                        )
                    )
                    preview = image_generation_probe_preview(img_response)
                return await record_gateway_model_test_success(
                    self._models,
                    model_id,
                    tested_at,
                    litellm_model,
                    response_preview=preview,
                    **record_kw,
                )
            if capability == "embedding":
                if should_use_dashscope_direct_embedding(target.provider):
                    embed_req = build_dashscope_embedding_request(
                        api_key=cred.api_key,
                        api_base=cred.api_base,
                        model_id=target.real_model,
                        input_payload=["ping"],
                    )
                    await perform_dashscope_embedding(embed_req)
                else:
                    await aembedding(
                        **_litellm_kw(
                            {
                                "model": litellm_model,
                                "input": ["ping"],
                                "api_key": cred.api_key,
                                "api_base": cred.api_base,
                            }
                        )
                    )
                return await record_gateway_model_test_success(
                    self._models, model_id, tested_at, litellm_model, **record_kw
                )
            if capability == "video_generation":
                if should_use_volcengine_direct_video(target.provider):
                    request = build_volcengine_video_create_request(
                        api_key=cred.api_key,
                        api_base=cred.api_base,
                        model_id=target.real_model,
                        prompt="ping",
                        seconds="5",
                    )
                    task_data = await perform_volcengine_video_create(
                        request,
                        timeout=VIDEO_PROBE_TIMEOUT,
                    )
                    video_response = map_volcengine_video_task_to_openai(
                        task_data,
                        fallback_model=target.real_model,
                    )
                else:
                    video_response = await avideo_generation(
                        **_litellm_kw(
                            {
                                "model": litellm_model,
                                "prompt": "ping",
                                "seconds": "5",
                                "api_key": cred.api_key,
                                "api_base": cred.api_base,
                                "timeout": VIDEO_PROBE_TIMEOUT,
                            }
                        )
                    )
                preview = video_generation_probe_preview(video_response)
                return await record_gateway_model_test_success(
                    self._models,
                    model_id,
                    tested_at,
                    litellm_model,
                    response_preview=preview,
                    **record_kw,
                )
            raise AssertionError(
                f"test_gateway_model: capability {capability!r} missing probe branch "
                "(out of sync with GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES)"
            )
        except Exception as exc:
            logger.warning("Gateway model %s connection test failed: %s", model_id, exc)
            msg = f"连接失败: {exc}"
            return await record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model, **record_kw
            )


__all__ = ["ProbeWritesMixin"]
