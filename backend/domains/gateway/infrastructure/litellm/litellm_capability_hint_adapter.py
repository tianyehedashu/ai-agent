"""LiteLLM 模型能力提示（基础设施；唯一 litellm 导入点之一）。"""

from __future__ import annotations

from typing import Any, cast

from domains.gateway.domain.litellm.litellm_capability_mapping import (
    LitellmModelInfoHints,
    hints_from_model_info,
)
from domains.gateway.domain.provider.provider_inference import infer_provider_name


class LitellmCapabilityHintAdapter:
    """通过 ``litellm.get_model_info`` 查询；未映射模型返回 None。"""

    @staticmethod
    def _resolve_model_id(provider: str, real_model: str) -> str:
        rm = (real_model or "").strip()
        prov = (provider or "").strip().lower()
        if "/" in rm:
            return rm
        if prov and rm:
            return f"{prov}/{rm}"
        return rm

    @staticmethod
    def _bare_model_id(real_model: str) -> str:
        rm = (real_model or "").strip()
        if "/" in rm:
            return rm.split("/", 1)[1]
        return rm

    def _candidate_model_ids(self, *, provider: str, real_model: str) -> tuple[str, ...]:
        """凭据 provider 优先；失败时 fallback 到模型 id 语义 provider（如 kimi → moonshot）。"""
        candidates: list[str] = []
        primary = self._resolve_model_id(provider, real_model)
        if primary:
            candidates.append(primary)
        semantic = infer_provider_name(real_model).strip().lower()
        bare = self._bare_model_id(real_model)
        if semantic and bare:
            fallback = f"{semantic}/{bare}"
            if fallback not in candidates:
                candidates.append(fallback)
        return tuple(candidates)

    @staticmethod
    def _fetch_model_info(model_id: str) -> dict[str, Any] | None:
        try:
            import litellm
        except ImportError:
            return None
        try:
            raw = litellm.get_model_info(model=model_id)
        except Exception:
            return None
        return cast("dict[str, Any]", raw)

    def get_model_hints(self, *, provider: str, real_model: str) -> LitellmModelInfoHints | None:
        for model_id in self._candidate_model_ids(provider=provider, real_model=real_model):
            raw = self._fetch_model_info(model_id)
            if raw is not None:
                return hints_from_model_info(raw)
        return None

    def supports_reasoning(self, *, provider: str, real_model: str) -> bool | None:
        hints = self.get_model_hints(provider=provider, real_model=real_model)
        if hints is None:
            return None
        value = hints.get("supports_reasoning")
        return value if isinstance(value, bool) else None


__all__ = ["LitellmCapabilityHintAdapter"]
