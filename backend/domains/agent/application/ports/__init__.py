"""Agent application 端口（跨域依赖倒置）。"""

from domains.agent.application.ports.model_catalog_port import (
    ModelCapabilitySnapshot,
    ModelCatalogPort,
)

__all__ = ["ModelCapabilitySnapshot", "ModelCatalogPort"]
