"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from typing import Any
import uuid

from bootstrap.config import settings as _settings
from domains.gateway.application.management.model_test_constants import (
    GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES,
)
from domains.gateway.domain.errors import (
    ManagementEntityNotFoundError,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
)
from libs.crypto import decrypt_value, derive_encryption_key
from libs.llm.litellm_model_id import build_litellm_model_id
from libs.model_connectivity import truncate_last_test_reason
from utils.logging import get_logger

logger = get_logger(__name__)


def _gateway_image_probe_size(provider: str) -> str:
    """生图探活用最小合法尺寸（各云厂商约束不同，与 Agent 侧 Seedream 默认对齐）。"""
    if provider == 'volcengine':
        return '1920x1920'
    if provider == 'openai':
        return '1024x1024'
    return '1024x1024'

async def _record_gateway_model_test_failure(models: GatewayModelRepository, model_id: uuid.UUID, tested_at: datetime, msg: str, litellm_model: str) -> dict[str, Any]:
    reason = truncate_last_test_reason(msg)
    await models.update(model_id, last_test_status='failed', last_tested_at=tested_at, last_test_reason=reason)
    return {'success': False, 'message': msg, 'model': litellm_model, 'status': 'failed', 'tested_at': tested_at, 'reason': reason}

async def _record_gateway_model_test_success(models: GatewayModelRepository, model_id: uuid.UUID, tested_at: datetime, litellm_model: str, *, response_preview: str | None=None) -> dict[str, Any]:
    await models.update(model_id, last_test_status='success', last_tested_at=tested_at, last_test_reason=None)
    payload: dict[str, Any] = {'success': True, 'message': '连接成功', 'model': litellm_model, 'status': 'success', 'tested_at': tested_at, 'reason': None}
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
        team_id = await self._ensure_personal_team_id(user_id)
        return await self.test_gateway_model(model_id, team_id=team_id)

    async def test_gateway_model(self, model_id: uuid.UUID, *, team_id: uuid.UUID) -> dict[str, Any]:
        """对 Gateway 团队模型发起一次最小调用做连通性测试（chat / embedding / 生图）。

            - 仅支持 ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES`` 中的 capability；
              其它返回 ``success=false`` + ``status=failed`` 并写回字段，避免前端误以为"未测过"。
            - 直连 ``litellm.acompletion`` / ``litellm.aimage_generation`` /
              ``litellm.aembedding`` 并显式传入解密后的 ``api_key`` 与 ``api_base``，
              绕过 Gateway 内部桥接，确保探测的就是这条记录本身的凭据。
            无论成功/失败，均把 ``last_test_status`` + ``last_tested_at`` +
            ``last_test_reason`` 写回 ``gateway_models``，列表页可直接展示连通状态。
            """
        existing = await self._models.get(model_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise ManagementEntityNotFoundError('model', str(model_id))
        capability = existing.capability
        litellm_model = build_litellm_model_id(existing.provider, existing.real_model)
        tested_at = datetime.now(UTC)
        if capability not in GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES:
            msg = f'capability={capability} 暂不支持连通性测试'
            return await _record_gateway_model_test_failure(self._models, model_id, tested_at, msg, litellm_model)
        credential = await self._creds.get(existing.credential_id)
        if credential is None:
            msg = '关联凭据已不存在'
            return await _record_gateway_model_test_failure(self._models, model_id, tested_at, msg, litellm_model)
        encryption_key = derive_encryption_key(_settings.secret_key.get_secret_value())
        try:
            api_key = decrypt_value(credential.api_key_encrypted, encryption_key)
        except Exception as exc:
            logger.warning('Failed to decrypt credential %s: %s', credential.id, exc)
            msg = f'凭据解密失败: {exc}'
            return await _record_gateway_model_test_failure(self._models, model_id, tested_at, msg, litellm_model)
        api_base = credential.api_base
        from litellm import acompletion, aembedding, aimage_generation
        try:
            if capability == 'chat':
                response = await acompletion(model=litellm_model, messages=[{'role': 'user', 'content': 'Hi'}], max_tokens=10, temperature=0, api_key=api_key, api_base=api_base)
                preview = ''
                with suppress(Exception):
                    preview = (response.choices[0].message.content or '')[:100]
                return await _record_gateway_model_test_success(self._models, model_id, tested_at, litellm_model, response_preview=preview)
            if capability == 'image':
                img_size = _gateway_image_probe_size(existing.provider)
                img_response = await aimage_generation(model=litellm_model, prompt='ping', n=1, size=img_size, api_key=api_key, api_base=api_base, timeout=60)
                preview = _image_generation_probe_preview(img_response)
                return await _record_gateway_model_test_success(self._models, model_id, tested_at, litellm_model, response_preview=preview)
            if capability == 'embedding':
                await aembedding(model=litellm_model, input=['ping'], api_key=api_key, api_base=api_base)
                return await _record_gateway_model_test_success(self._models, model_id, tested_at, litellm_model)
            raise AssertionError(f'test_gateway_model: capability {capability!r} missing probe branch (out of sync with GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES)')
        except Exception as exc:
            logger.warning('Gateway model %s connection test failed: %s', model_id, exc)
            msg = f'连接失败: {exc}'
            return await _record_gateway_model_test_failure(self._models, model_id, tested_at, msg, litellm_model)
