"""OpenAI 兼容 ``GET .../models`` 的 httpx 适配器。"""

from __future__ import annotations

from typing import Any

import httpx

from domains.gateway.application.management.ports import (
    RawUpstreamListResult,
    UpstreamModelListPort,
)


class OpenAICompatibleModelListAdapter(UpstreamModelListPort):
    async def fetch_models(
        self,
        *,
        list_url: str,
        api_key: str,
        timeout_seconds: float = 15.0,
        user_agent: str | None = None,
    ) -> RawUpstreamListResult:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        if user_agent:
            headers["User-Agent"] = user_agent
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                resp = await client.get(list_url, headers=headers)
        except httpx.TimeoutException:
            return RawUpstreamListResult(
                ok=False,
                http_status=None,
                items=(),
                error_message="连接上游超时，请检查网络或稍后重试。",
            )
        except httpx.RequestError as exc:
            return RawUpstreamListResult(
                ok=False,
                http_status=None,
                items=(),
                error_message=f"无法连接上游：{type(exc).__name__}",
            )

        if resp.status_code != 200:
            detail = _safe_error_detail(resp)
            return RawUpstreamListResult(
                ok=False,
                http_status=resp.status_code,
                items=(),
                error_message=detail or f"上游返回 HTTP {resp.status_code}",
            )

        try:
            payload: dict[str, Any] = resp.json()
        except ValueError:
            return RawUpstreamListResult(
                ok=False,
                http_status=resp.status_code,
                items=(),
                error_message="上游响应不是合法 JSON。",
            )

        raw_data = payload.get("data")
        if not isinstance(raw_data, list):
            return RawUpstreamListResult(
                ok=False,
                http_status=resp.status_code,
                items=(),
                error_message="上游 JSON 缺少 data 列表字段。",
            )

        rows: list[tuple[str, str | None]] = []
        for entry in raw_data:
            if not isinstance(entry, dict):
                continue
            mid = entry.get("id")
            if not isinstance(mid, str) or not mid.strip():
                continue
            ob = entry.get("owned_by")
            owned = ob if isinstance(ob, str) else None
            rows.append((mid.strip(), owned))

        return RawUpstreamListResult(
            ok=True,
            http_status=resp.status_code,
            items=tuple(rows),
            error_message=None,
        )


def _safe_error_detail(resp: httpx.Response) -> str | None:
    try:
        body = resp.json()
    except ValueError:
        text = resp.text
        return text[:500] if text else None
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            msg = err.get("message")
            if isinstance(msg, str):
                return msg[:500]
        msg2 = body.get("message")
        if isinstance(msg2, str):
            return msg2[:500]
    return None


__all__ = ["OpenAICompatibleModelListAdapter"]
