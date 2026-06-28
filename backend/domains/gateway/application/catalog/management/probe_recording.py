"""模型连通性探活：测试结果写回仓储。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from libs.model_connectivity import truncate_last_test_reason


async def record_gateway_model_test_failure(
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
            last_test_status="failed",
            last_tested_at=tested_at,
            last_test_reason=reason,
        )
    else:
        await models.update(
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


async def record_gateway_model_test_success(
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
            last_test_status="success",
            last_tested_at=tested_at,
            last_test_reason=None,
        )
    else:
        await models.update(
            model_id,
            last_test_status="success",
            last_tested_at=tested_at,
            last_test_reason=None,
        )
    payload: dict[str, Any] = {
        "success": True,
        "message": "连接成功",
        "model": litellm_model,
        "status": "success",
        "tested_at": tested_at,
        "reason": None,
    }
    if response_preview is not None:
        payload["response_preview"] = response_preview
    return payload


__all__ = ["record_gateway_model_test_failure", "record_gateway_model_test_success"]
