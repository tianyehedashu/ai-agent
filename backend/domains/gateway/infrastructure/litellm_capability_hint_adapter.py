"""LiteLLM 模型能力提示（基础设施；唯一 litellm 导入点之一）。"""

from __future__ import annotations

from typing import Any, cast

from domains.gateway.domain.litellm_capability_mapping import (
    LitellmModelInfoHints,
    hints_from_model_info,
)


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

    def get_model_hints(self, *, provider: str, real_model: str) -> LitellmModelInfoHints | None:
        model_id = self._resolve_model_id(provider, real_model)
        if not model_id:
            return None
        try:
            import litellm
        except ImportError:
            return None
        try:
            raw = litellm.get_model_info(model=model_id)
        except Exception:
            return None
        return hints_from_model_info(cast("dict[str, Any]", raw))

    def supports_reasoning(self, *, provider: str, real_model: str) -> bool | None:
        hints = self.get_model_hints(provider=provider, real_model=real_model)
        if hints is None:
            return None
        value = hints.get("supports_reasoning")
        return value if isinstance(value, bool) else None


__all__ = ["LitellmCapabilityHintAdapter"]
