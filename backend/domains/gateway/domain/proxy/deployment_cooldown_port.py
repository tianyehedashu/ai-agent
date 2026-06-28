"""Deployment cooldown 端口（domain 契约，infrastructure 实现）。

将 "把某个 deployment 标记为暂时不可用" 的语义抽象为 domain 层可依赖的端口，
避免 application 层直接耦合 LiteLLM Router 实现细节。
"""

from __future__ import annotations

from typing import Protocol


class DeploymentCooldownPort(Protocol):
    """将指定 deployment 标记为暂时不可用；具体冷却时长由实现决定。"""

    async def cooldown_deployment(
        self,
        *,
        deployment_id: str,
        reason: str,
    ) -> None:
        """标记 deployment 进入 cooldown。

        Args:
            deployment_id: GatewayModel / Router deployment 的 stable id。
            reason: 触发 cooldown 的原因，仅用于日志/可观测性。
        """
        ...


__all__ = ["DeploymentCooldownPort"]
