"""凭据跨 scope 复制/导入 application 层结果 DTO。"""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid

from domains.gateway.application.management.credential_read_model import CredentialReadModel


@dataclass
class ImportedModelSummary:
    """复制过程中成功创建的单个模型摘要。"""

    source_model_id: str | None
    name: str
    real_model: str


@dataclass
class ModelImportFailure:
    """单条模型复制失败记录。"""

    model_name: str
    reason: str


@dataclass
class CredentialImportFailure:
    """单条凭据复制失败记录。"""

    credential_id: str
    reason: str


@dataclass
class ImportedCredentialItem:
    """单条凭据复制成功及其关联模型。"""

    source_credential_id: uuid.UUID
    new_credential_id: uuid.UUID
    new_credential_name: str
    new_credential_read: CredentialReadModel
    provider: str
    models_created: list[ImportedModelSummary]
    models_failed: list[ModelImportFailure]


@dataclass
class ImportCredentialsWithModelsResult:
    """批量凭据 + 模型复制聚合结果。"""

    succeeded: list[ImportedCredentialItem] = field(default_factory=list)
    failed: list[CredentialImportFailure] = field(default_factory=list)


__all__ = [
    "CredentialImportFailure",
    "ImportCredentialsWithModelsResult",
    "ImportedCredentialItem",
    "ImportedModelSummary",
    "ModelImportFailure",
]
