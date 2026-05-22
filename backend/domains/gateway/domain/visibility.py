"""系统级 Gateway 资源可见性（public / restricted / inherit）。"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
import uuid  # noqa: TC003 — used only in postponed annotations

from domains.gateway.domain.errors import InvalidSystemVisibilityError

SubjectKind = Literal["credential", "model"]
TargetKind = Literal["team", "user"]
CredentialVisibility = Literal["public", "restricted"]
ModelVisibility = Literal["inherit", "public", "restricted"]


class Visibility(StrEnum):
    PUBLIC = "public"
    RESTRICTED = "restricted"
    INHERIT = "inherit"


def effective_visibility(
    model_visibility: str,
    credential_visibility: str,
) -> Visibility:
    """解析模型最终可见性：inherit 时跟随凭据。"""
    raw = (model_visibility or Visibility.INHERIT.value).strip().lower()
    if raw == Visibility.INHERIT.value:
        cred_raw = (credential_visibility or Visibility.PUBLIC.value).strip().lower()
        if cred_raw == Visibility.RESTRICTED.value:
            return Visibility.RESTRICTED
        return Visibility.PUBLIC
    if raw == Visibility.RESTRICTED.value:
        return Visibility.RESTRICTED
    return Visibility.PUBLIC


def is_subject_granted(
    *,
    subject_kind: SubjectKind,
    subject_id: uuid.UUID,
    credential_id: uuid.UUID,
    granted_subject_keys: set[tuple[str, uuid.UUID]],
) -> bool:
    """模型级与凭据级 grant 取并集。"""
    if (subject_kind, subject_id) in granted_subject_keys:
        return True
    return ("credential", credential_id) in granted_subject_keys


def credential_visibility_for_api(raw: str | None) -> CredentialVisibility | None:
    """将仓储 visibility 规范为 API 允许的凭据可见性。"""
    v = (raw or "").strip().lower()
    if v == Visibility.PUBLIC.value:
        return "public"
    if v == Visibility.RESTRICTED.value:
        return "restricted"
    return None


def assert_credential_visibility_value(value: str) -> CredentialVisibility:
    parsed = credential_visibility_for_api(value)
    if parsed is None:
        raise InvalidSystemVisibilityError(f"Invalid credential visibility: {value}")
    return parsed


def assert_model_visibility_value(value: str) -> ModelVisibility:
    v = (value or "").strip().lower()
    if v == Visibility.INHERIT.value:
        return "inherit"
    if v == Visibility.PUBLIC.value:
        return "public"
    if v == Visibility.RESTRICTED.value:
        return "restricted"
    raise InvalidSystemVisibilityError(f"Invalid model visibility: {value}")


def assert_subject_kind(value: str) -> SubjectKind:
    if value == "credential":
        return "credential"
    if value == "model":
        return "model"
    raise InvalidSystemVisibilityError(f"Invalid subject_kind: {value}")


def assert_target_kind(value: str) -> TargetKind:
    if value == "team":
        return "team"
    if value == "user":
        return "user"
    raise InvalidSystemVisibilityError(f"Invalid target_kind: {value}")


__all__ = [
    "CredentialVisibility",
    "ModelVisibility",
    "SubjectKind",
    "TargetKind",
    "Visibility",
    "assert_credential_visibility_value",
    "assert_model_visibility_value",
    "assert_subject_kind",
    "assert_target_kind",
    "credential_visibility_for_api",
    "effective_visibility",
    "is_subject_granted",
]
