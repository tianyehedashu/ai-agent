"""LiteLLM 模型能力提示（基础设施；唯一 litellm 导入点之一）。"""

from __future__ import annotations

from typing import Protocol


class LitellmCapabilityHintPort(Protocol):
    """查询 LiteLLM 内置价目表中的能力标记。"""

    def supports_reasoning(self, *, provider: str, real_model: str) -> bool | None:
        """已映射且支持 reasoning 返回 True/False；未映射返回 None。"""


class LitellmCapabilityHintAdapter:
    """通过 ``litellm.supports_reasoning`` 查询；未映射模型返回 None。"""

    def supports_reasoning(self, *, provider: str, real_model: str) -> bool | None:
        try:
            import litellm
        except ImportError:
            return None

        rm = (real_model or "").strip()
        prov = (provider or "").strip().lower()
        if "/" in rm:
            model_id = rm
        elif prov and rm:
            model_id = f"{prov}/{rm}"
        else:
            model_id = rm
        if not model_id:
            return None
        try:
            return bool(litellm.supports_reasoning(model=model_id))
        except Exception:
            return None


__all__ = ["LitellmCapabilityHintAdapter", "LitellmCapabilityHintPort"]
