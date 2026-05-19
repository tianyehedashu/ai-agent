"""Agent application 端口（跨域依赖倒置）。"""

from domains.agent.application.ports.message_port import MessageApplicationPort
from domains.agent.application.ports.model_catalog_port import (
    ModelCapabilitySnapshot,
    ModelCatalogPort,
)
from domains.agent.application.ports.video_task_port import VideoTaskApplicationPort

__all__ = [
    "MessageApplicationPort",
    "ModelCapabilitySnapshot",
    "ModelCatalogPort",
    "VideoTaskApplicationPort",
]
