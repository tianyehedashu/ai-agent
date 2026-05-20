"""Agent application 端口（跨域依赖倒置）。"""

from domains.agent.application.ports.message_port import MessageApplicationPort
from domains.agent.application.ports.model_catalog_port import (
    ModelCapabilitySnapshot,
    ModelCatalogPort,
)
from domains.agent.application.ports.text_embedding_port import TextEmbeddingPort
from domains.agent.application.ports.vector_index_port import VectorHit, VectorIndexPort
from domains.agent.application.ports.video_task_port import VideoTaskApplicationPort

__all__ = [
    "MessageApplicationPort",
    "ModelCapabilitySnapshot",
    "ModelCatalogPort",
    "TextEmbeddingPort",
    "VectorHit",
    "VectorIndexPort",
    "VideoTaskApplicationPort",
]
