"""将 user_models 迁入 personal team gateway_models（幂等）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import func, select, text

from bootstrap.config import settings
from domains.gateway.application.personal_models import (
    capability_for_model_type,
    personal_model_alias,
    tags_for_model_type,
)
from domains.gateway.domain.litellm_model_id import build_litellm_model_id
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key
from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Session

from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from domains.tenancy.infrastructure.models.team import Team, TeamMember

logger = get_logger(__name__)

_SELECT_USER_MODELS = text(
    """
    SELECT id, user_id, display_name, provider, model_id, api_key_encrypted, api_base,
           model_types, config, is_active, last_test_status, last_tested_at, last_test_reason
    FROM user_models
    WHERE user_id IS NOT NULL
    """
)


async def migrate_user_models_to_personal_gateway(session: AsyncSession) -> dict[str, int]:
    """迁移已登录用户的 user_models → personal team gateway_models + user 凭据。"""
    _ = derive_encryption_key(settings.secret_key.get_secret_value())
    teams = TeamService(session)
    creds = ProviderCredentialRepository(session)
    models = GatewayModelRepository(session)

    result = await session.execute(_SELECT_USER_MODELS)
    rows = [dict(r._mapping) for r in result.mappings()]

    migrated_models = 0
    skipped_no_key = 0
    skipped_already = 0

    for um in rows:
        user_id = um["user_id"]
        if user_id is None:
            continue
        personal_team = await teams.ensure_personal_team(user_id)
        team_id = personal_team.id

        existing = await models.list_tenant_owned(team_id, only_enabled=False)
        if any(
            str((m.tags or {}).get("display_name") or "") == um["display_name"]
            and m.provider == um["provider"]
            for m in existing
        ):
            skipped_already += 1
            continue

        if not um.get("api_key_encrypted"):
            skipped_no_key += 1
            logger.info("Skip user_model %s: no api_key", um["id"])
            continue

        cred_name = f"migrated-{um['provider']}-{str(um['id'])[:8]}"
        cred = await creds.create(
            scope="user",
            scope_id=user_id,
            provider=um["provider"],
            name=cred_name,
            api_key_encrypted=um["api_key_encrypted"],
            api_base=um.get("api_base"),
            extra=None,
            is_active=True,
        )

        model_types = list(um.get("model_types") or ["text"])
        for idx, mtype in enumerate(model_types):
            cap = capability_for_model_type(mtype)
            alias = personal_model_alias(um["display_name"], mtype, suffix=idx if idx else 0)
            suffix = 0
            while await models.name_exists_for_tenant(team_id, alias):
                suffix += 1
                alias = personal_model_alias(um["display_name"], mtype, suffix=suffix)

            tags: dict[str, Any] = tags_for_model_type(mtype)
            tags["display_name"] = um["display_name"]
            config = um.get("config")
            if isinstance(config, dict):
                tags.update({k: v for k, v in config.items() if v is not None})

            real_model = build_litellm_model_id(um["provider"], um["model_id"])
            row = await models.create(
                tenant_id=team_id,
                name=alias,
                capability=cap,
                real_model=real_model,
                credential_id=cred.id,
                provider=um["provider"],
                weight=1,
                rpm_limit=None,
                tpm_limit=None,
                tags=tags,
            )
            await models.update(
                row.id,
                enabled=bool(um.get("is_active", True)),
                last_test_status=um.get("last_test_status"),
                last_tested_at=um.get("last_tested_at"),
                last_test_reason=um.get("last_test_reason"),
            )
            migrated_models += 1

        await session.flush()

    return {
        "source_rows": len(rows),
        "migrated_model_rows": migrated_models,
        "skipped_no_key": skipped_no_key,
        "skipped_already": skipped_already,
    }


def _ensure_personal_team_sync(session: Session, user_id: uuid.UUID) -> Team:
    stmt = (
        select(Team)
        .where(
            Team.owner_user_id == user_id,
            Team.kind == "personal",
            Team.is_active.is_(True),
        )
        .order_by(Team.created_at.asc(), Team.id.asc())
        .limit(1)
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing
    team = Team(
        name="Personal",
        slug=f"personal-{user_id}",
        kind="personal",
        owner_user_id=user_id,
        settings={},
        is_active=True,
    )
    session.add(team)
    session.flush()
    session.add(TeamMember(tenant_id=team.id, user_id=user_id, role="owner"))
    session.flush()
    return team


def _list_tenant_owned_sync(session: Session, tenant_id: uuid.UUID) -> list[GatewayModel]:
    stmt = select(GatewayModel).where(GatewayModel.tenant_id == tenant_id)
    return list(session.execute(stmt).scalars().all())


def _name_exists_for_tenant_sync(session: Session, tenant_id: uuid.UUID, name: str) -> bool:
    stmt = (
        select(func.count())
        .select_from(GatewayModel)
        .where(GatewayModel.tenant_id == tenant_id, GatewayModel.name == name)
    )
    return int(session.execute(stmt).scalar_one() or 0) > 0


def migrate_user_models_to_personal_gateway_sync(session: Session) -> dict[str, int]:
    """Alembic 专用：在 ``op.get_bind()`` 的同一事务/连接上迁移（避免第二连接死锁）。"""
    _ = derive_encryption_key(settings.secret_key.get_secret_value())

    result = session.execute(_SELECT_USER_MODELS)
    rows = [dict(r._mapping) for r in result.mappings()]

    migrated_models = 0
    skipped_no_key = 0
    skipped_already = 0

    for um in rows:
        user_id = um["user_id"]
        if user_id is None:
            continue
        personal_team = _ensure_personal_team_sync(session, user_id)
        team_id = personal_team.id

        existing = _list_tenant_owned_sync(session, team_id)
        if any(
            str((m.tags or {}).get("display_name") or "") == um["display_name"]
            and m.provider == um["provider"]
            for m in existing
        ):
            skipped_already += 1
            continue

        if not um.get("api_key_encrypted"):
            skipped_no_key += 1
            logger.info("Skip user_model %s: no api_key", um["id"])
            continue

        cred_name = f"migrated-{um['provider']}-{str(um['id'])[:8]}"
        cred = ProviderCredential(
            scope="user",
            scope_id=user_id,
            provider=um["provider"],
            name=cred_name,
            api_key_encrypted=um["api_key_encrypted"],
            api_base=um.get("api_base"),
            extra=None,
            is_active=True,
        )
        session.add(cred)
        session.flush()

        model_types = list(um.get("model_types") or ["text"])
        for idx, mtype in enumerate(model_types):
            cap = capability_for_model_type(mtype)
            alias = personal_model_alias(um["display_name"], mtype, suffix=idx if idx else 0)
            suffix = 0
            while _name_exists_for_tenant_sync(session, team_id, alias):
                suffix += 1
                alias = personal_model_alias(um["display_name"], mtype, suffix=suffix)

            tags: dict[str, Any] = tags_for_model_type(mtype)
            tags["display_name"] = um["display_name"]
            config = um.get("config")
            if isinstance(config, dict):
                tags.update({k: v for k, v in config.items() if v is not None})

            real_model = build_litellm_model_id(um["provider"], um["model_id"])
            row = GatewayModel(
                tenant_id=team_id,
                name=alias,
                capability=cap,
                real_model=real_model,
                credential_id=cred.id,
                provider=um["provider"],
                weight=1,
                rpm_limit=None,
                tpm_limit=None,
                tags=tags,
                enabled=bool(um.get("is_active", True)),
                last_test_status=um.get("last_test_status"),
                last_tested_at=um.get("last_tested_at"),
                last_test_reason=um.get("last_test_reason"),
                created_by_user_id=user_id,
            )
            session.add(row)
            migrated_models += 1

        session.flush()

    logger.info(
        "user_models migration done: source=%s migrated=%s skipped_no_key=%s skipped_already=%s",
        len(rows),
        migrated_models,
        skipped_no_key,
        skipped_already,
    )
    return {
        "source_rows": len(rows),
        "migrated_model_rows": migrated_models,
        "skipped_no_key": skipped_no_key,
        "skipped_already": skipped_already,
    }


__all__ = [
    "migrate_user_models_to_personal_gateway",
    "migrate_user_models_to_personal_gateway_sync",
]
