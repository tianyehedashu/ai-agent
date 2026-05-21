"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
import uuid

from bootstrap.config import settings as _settings
from domains.gateway.application.management.model_test_constants import (
    GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES,
)
from domains.gateway.domain.errors import (
    ManagementEntityNotFoundError,
)
from domains.gateway.domain.litellm_model_id import build_litellm_model_id
from domains.gateway.domain.policies.volcengine_image_probe import (
    build_volcengine_image_probe_request,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
)
from domains.gateway.infrastructure.upstream.volcengine_image_probe_client import (
    perform_volcengine_image_probe,
)
from libs.crypto import decrypt_value, derive_encryption_key
from libs.model_connectivity import truncate_last_test_reason
from utils.logging import get_logger

logger = get_logger(__name__)


class _EncryptedCredential(Protocol):
    id: uuid.UUID
    api_key_encrypted: str
    api_base: str | None
    extra: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class _ProbeTarget:
    model_id: uuid.UUID
    capability: str
    provider: str
    real_model: str
    credential_id: uuid.UUID
    is_system: bool


def _gateway_image_probe_size(provider: str) -> str:
    """生图探活用最小合法尺寸（各云厂商约束不同，与 Agent 侧 Seedream 默认对齐）。"""
    if provider == 'volcengine':
        return '1920x1920'
    if provider == 'openai':
        return '1024x1024'
    return '1024x1024'


async def _record_gateway_model_test_failure(
    models: GatewayModelRepository,
    model_id: uuid.UUID,
    tested_at: datetime,
    msg: str,
    litellm_model: str,
    *,
    is_system: bool,
) -> dict[str, Any]:
    reason = truncate_last_test_reason(msg)
    if is_system:
        await models.update_system(
            model_id,
            last_test_status='failed',
            last_tested_at=tested_at,
            last_test_reason=reason,
        )
    else:
        await models.update(
            model_id,
            last_test_status='failed',
            last_tested_at=tested_at,
            last_test_reason=reason,
        )
    return {
        'success': False,
        'message': msg,
        'model': litellm_model,
        'status': 'failed',
        'tested_at': tested_at,
        'reason': reason,
    }


async def _record_gateway_model_test_success(
    models: GatewayModelRepository,
    model_id: uuid.UUID,
    tested_at: datetime,
    litellm_model: str,
    *,
    is_system: bool,
    response_preview: str | None = None,
) -> dict[str, Any]:
    if is_system:
        await models.update_system(
            model_id,
            last_test_status='success',
            last_tested_at=tested_at,
            last_test_reason=None,
        )
    else:
        await models.update(
            model_id,
            last_test_status='success',
            last_tested_at=tested_at,
            last_test_reason=None,
        )
    payload: dict[str, Any] = {
        'success': True,
        'message': '连接成功',
        'model': litellm_model,
        'status': 'success',
        'tested_at': tested_at,
        'reason': None,
    }
    if response_preview is not None:
        payload['response_preview'] = response_preview
    return payload


def _image_generation_probe_preview(img_response: Any) -> str:
    preview = ''
    with suppress(Exception):
        data = getattr(img_response, 'data', None)
        if data is None and isinstance(img_response, dict):
            raw = img_response.get('data')
            data = raw if isinstance(raw, list) else None
        if data and len(data) > 0:
            first = data[0]
            url: str | None
            b64: str | None
            if isinstance(first, dict):
                url = first.get('url') if isinstance(first.get('url'), str) else None
                b64 = first.get('b64_json') if isinstance(first.get('b64_json'), str) else None
            else:
                url = getattr(first, 'url', None)
                b64 = getattr(first, 'b64_json', None)
                url = url if isinstance(url, str) else None
                b64 = b64 if isinstance(b64, str) else None
            if url:
                preview = url[:100]
            elif b64:
                preview = f'{b64[:40]}…' if len(b64) > 40 else b64
    return preview


class ProbeWritesMixin:
    """模型连通性探活。"""

    async def test_personal_model(self, user_id: uuid.UUID, model_id: uuid.UUID) -> dict[str, Any]:
        tenant_id = await self._ensure_personal_tenant_id(user_id)
        return await self.test_gateway_model(model_id, tenant_id=tenant_id)

    async def _resolve_probe_target(
        self,
        model_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
    ) -> _ProbeTarget:
        tenant_row = await self._models.get(model_id)
        if tenant_row is not None:
            if tenant_row.tenant_id is not None and tenant_row.tenant_id != tenant_id:
                raise ManagementEntityNotFoundError('model', str(model_id))
            return _ProbeTarget(
                model_id=model_id,
                capability=tenant_row.capability,
                provider=tenant_row.provider,
                real_model=tenant_row.real_model,
                credential_id=tenant_row.credential_id,
                is_system=False,
            )
        system_row = await self._models.get_system(model_id)
        if system_row is None:
            raise ManagementEntityNotFoundError('model', str(model_id))
        return _ProbeTarget(
            model_id=model_id,
            capability=system_row.capability,
            provider=system_row.provider,
            real_model=system_row.real_model,
            credential_id=system_row.credential_id,
            is_system=True,
        )

    async def _load_probe_credential(
        self,
        target: _ProbeTarget,
    ) -> _EncryptedCredential | None:
        if target.is_system:
            return await self._system_creds.get(target.credential_id)
        return await self._creds.get(target.credential_id)

    async def test_gateway_model(self, model_id: uuid.UUID, *, tenant_id: uuid.UUID) -> dict[str, Any]:
        """对 Gateway 模型发起一次最小调用做连通性测试（chat / embedding / 生图）。

            - 支持租户 ``gateway_models`` 与 ``list_for_tenant`` 可见的 ``system_gateway_models``；
            - 仅支持 ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES`` 中的 capability；
              其它返回 ``success=false`` + ``status=failed`` 并写回字段，避免前端误以为"未测过"。
            - 直连 ``litellm.acompletion`` / ``litellm.aimage_generation`` /
              ``litellm.aembedding`` 并显式传入解密后的 ``api_key`` 与 ``api_base``，
              绕过 Gateway 内部桥接，确保探测的就是这条记录本身的凭据。
            无论成功/失败，均把 ``last_test_status`` + ``last_tested_at`` +
            ``last_test_reason`` 写回对应表，列表页可直接展示连通状态。
            """
        target = await self._resolve_probe_target(model_id, tenant_id=tenant_id)
        capability = target.capability
        litellm_model = build_litellm_model_id(target.provider, target.real_model)
        tested_at = datetime.now(UTC)
        record_kw = {'is_system': target.is_system}
        if capability not in GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES:
            msg = f'capability={capability} 暂不支持连通性测试'
            return await _record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model, **record_kw
            )
        credential = await self._load_probe_credential(target)
        if credential is None:
            msg = '关联凭据已不存在'
            return await _record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model, **record_kw
            )
        encryption_key = derive_encryption_key(_settings.secret_key.get_secret_value())
        try:
            api_key = decrypt_value(credential.api_key_encrypted, encryption_key)
        except Exception as exc:
            logger.warning('Failed to decrypt credential %s: %s', credential.id, exc)
            msg = f'凭据解密失败: {exc}'
            return await _record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model, **record_kw
            )
        api_base = credential.api_base
        from litellm import acompletion, aembedding, aimage_generation
        try:
            if capability == 'chat':
                response = await acompletion(
                    model=litellm_model,
                    messages=[{'role': 'user', 'content': 'Hi'}],
                    max_tokens=10,
                    temperature=0,
                    api_key=api_key,
                    api_base=api_base,
                )
                preview = ''
                with suppress(Exception):
                    preview = (response.choices[0].message.content or '')[:100]
                return await _record_gateway_model_test_success(
                    self._models,
                    model_id,
                    tested_at,
                    litellm_model,
                    response_preview=preview,
                    **record_kw,
                )
            if capability == 'image':
                img_size = _gateway_image_probe_size(target.provider)
                if target.provider == 'volcengine':
                    image_endpoint = (credential.extra or {}).get('image_endpoint_id')
                    if not isinstance(image_endpoint, str) or not image_endpoint.strip():
                        msg = (
                            '未配置火山图像接入点（凭据 extra.image_endpoint_id 为空；'
                            '需设置 VOLCENGINE_IMAGE_ENDPOINT_ID 或在 BYOK 凭据 extra 中提供）'
                        )
                        return await _record_gateway_model_test_failure(
                            self._models, model_id, tested_at, msg, litellm_model, **record_kw
                        )
                    request = build_volcengine_image_probe_request(
                        api_key=api_key,
                        api_base=api_base,
                        image_endpoint_id=image_endpoint.strip(),
                        size=img_size,
                    )
                    img_data = await perform_volcengine_image_probe(request)
                    preview = _image_generation_probe_preview(img_data)
                else:
                    img_response = await aimage_generation(
                        model=litellm_model,
                        prompt='ping',
                        n=1,
                        size=img_size,
                        api_key=api_key,
                        api_base=api_base,
                        timeout=60,
                    )
                    preview = _image_generation_probe_preview(img_response)
                return await _record_gateway_model_test_success(
                    self._models,
                    model_id,
                    tested_at,
                    litellm_model,
                    response_preview=preview,
                    **record_kw,
                )
            if capability == 'embedding':
                await aembedding(
                    model=litellm_model,
                    input=['ping'],
                    api_key=api_key,
                    api_base=api_base,
                )
                return await _record_gateway_model_test_success(
                    self._models, model_id, tested_at, litellm_model, **record_kw
                )
            raise AssertionError(
                f'test_gateway_model: capability {capability!r} missing probe branch '
                '(out of sync with GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES)'
            )
        except Exception as exc:
            logger.warning('Gateway model %s connection test failed: %s', model_id, exc)
            msg = f'连接失败: {exc}'
            return await _record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model, **record_kw
            )
