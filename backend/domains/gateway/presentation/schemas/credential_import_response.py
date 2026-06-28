"""凭据批量导入/复制 API 响应组装。"""

from __future__ import annotations

from domains.gateway.application.credential.management.credential_copy_types import (
    ImportCredentialsWithModelsResult,
)
from domains.gateway.presentation.schemas.credential_import import (
    CredentialCopyFailureItem,
    ImportCredentialsWithModelsResponse,
    ImportedCredentialItemResponse,
    ImportedModelSummary,
    ModelImportFailureItem,
)
from domains.gateway.presentation.schemas.credential_response import build_credential_response


def build_import_credentials_with_models_response(
    result: ImportCredentialsWithModelsResult,
    *,
    encryption_key: str,
) -> ImportCredentialsWithModelsResponse:
    succeeded: list[ImportedCredentialItemResponse] = []
    for item in result.succeeded:
        cred_resp = build_credential_response(
            item.new_credential_read, encryption_key=encryption_key
        )
        succeeded.append(
            ImportedCredentialItemResponse(
                source_credential_id=item.source_credential_id,
                new_credential=cred_resp,
                models_created=[
                    ImportedModelSummary(
                        source_model_id=m.source_model_id,
                        name=m.name,
                        real_model=m.real_model,
                    )
                    for m in item.models_created
                ],
                models_failed=[
                    ModelImportFailureItem(model_name=m.model_name, reason=m.reason)
                    for m in item.models_failed
                ],
            )
        )
    return ImportCredentialsWithModelsResponse(
        succeeded=succeeded,
        failed=[
            CredentialCopyFailureItem(credential_id=f.credential_id, reason=f.reason)
            for f in result.failed
        ],
    )


__all__ = ["build_import_credentials_with_models_response"]
