"""migrate user_models rows into personal team gateway_models

Revision ID: 20260515_um_data
Revises: 20260515_gm_lum
Create Date: 2026-05-15

设计要点
--------
* **完全自包含**：仅依赖 alembic 自己的 ``op.get_bind()``（与 schema 迁移共享同一连接 +
  同一事务），不引入任何 ``domains.*`` / ``libs.*`` 业务代码，更不再开第二个数据库
  连接 —— 这是上一版死锁的根因（DDL 长事务占着 ``user_models`` 的强锁，第二条连接
  里的 ``SELECT user_models`` 永远等不到）。
* **工具函数内联快照**：``_slugify`` / ``_capability_for_type`` / ``_tags_for_type``
  / ``_personal_model_alias`` / ``_litellm_model_id`` 是当前业务代码的副本。迁移
  代表 *这一时点* 的语义，不能跟随未来业务漂移。
* **批量 SQL**：personal team / member 用一次集合化 INSERT 完成；凭据与 gateway_model
  按行 INSERT，去重和命名冲突在 Python 侧解决，全部使用同一 ``bind``。
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import text

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "20260515_um_data"
down_revision: str | None = "20260515_gm_lum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_LITELLM_PROVIDER_PREFIXES = frozenset({"dashscope", "deepseek", "volcengine"})

_MODEL_TYPE_TO_CAPABILITY: dict[str, str] = {
    "text": "chat",
    "image": "chat",
    "image_gen": "image",
    "video": "video_generation",
}


def _slugify(display_name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", display_name.strip().lower()).strip("-")
    return base[:80] if base else "model"


def _capability_for_type(model_type: str) -> str:
    return _MODEL_TYPE_TO_CAPABILITY.get(model_type, "chat")


def _tags_for_type(model_type: str) -> dict[str, Any]:
    if model_type == "image":
        return {"supports_vision": True}
    if model_type == "image_gen":
        return {"supports_image_gen": True}
    if model_type == "video":
        return {"supports_video_gen": True}
    return {}


def _personal_model_alias(display_name: str, model_type: str, *, suffix: int = 0) -> str:
    slug = _slugify(display_name)
    cap = _capability_for_type(model_type)
    parts = [slug, model_type if model_type != "text" else "", cap]
    if suffix > 0:
        parts.append(str(suffix))
    return "-".join(p for p in parts if p)[:200]


def _litellm_model_id(provider: str, model_id: str) -> str:
    if not model_id or "/" in model_id:
        return model_id
    if provider == "zhipuai":
        return f"zai/{model_id}"
    if provider in _LITELLM_PROVIDER_PREFIXES:
        return f"{provider}/{model_id}"
    return model_id


# --- SQL ---

_UPSERT_PERSONAL_TEAMS = text(
    """
    INSERT INTO gateway_teams (
        id, name, slug, kind, owner_user_id, settings, is_active, created_at, updated_at
    )
    SELECT
        gen_random_uuid(), 'Personal',
        'personal-' || u.user_id::text,
        'personal', u.user_id, '{}'::jsonb, true, now(), now()
    FROM (SELECT DISTINCT user_id FROM user_models WHERE user_id IS NOT NULL) u
    WHERE NOT EXISTS (
        SELECT 1 FROM gateway_teams t
        WHERE t.owner_user_id = u.user_id
          AND t.kind = 'personal'
          AND t.is_active = true
    )
    """
)

_UPSERT_PERSONAL_MEMBERS = text(
    """
    INSERT INTO gateway_team_members (
        id, team_id, user_id, role, created_at, updated_at
    )
    SELECT gen_random_uuid(), t.id, t.owner_user_id, 'owner', now(), now()
    FROM gateway_teams t
    WHERE t.kind = 'personal'
      AND t.is_active = true
      AND NOT EXISTS (
          SELECT 1 FROM gateway_team_members m
          WHERE m.team_id = t.id AND m.user_id = t.owner_user_id
      )
    """
)

_SELECT_USER_MODELS = text(
    """
    SELECT id, user_id, display_name, provider, model_id, api_key_encrypted, api_base,
           model_types, config, is_active, last_test_status, last_tested_at, last_test_reason
    FROM user_models
    WHERE user_id IS NOT NULL
    """
)

_SELECT_PERSONAL_TEAM_MAP = text(
    """
    SELECT owner_user_id, id
    FROM gateway_teams
    WHERE kind = 'personal' AND is_active = true
    """
)

_SELECT_EXISTING_PERSONAL_MODELS = text(
    """
    SELECT team_id, name, provider, COALESCE(tags->>'display_name', '') AS display_name
    FROM gateway_models
    WHERE team_id IS NOT NULL
    """
)

_INSERT_CREDENTIAL = text(
    """
    INSERT INTO provider_credentials (
        id, scope, scope_id, provider, name,
        api_key_encrypted, api_base, extra, is_active,
        created_at, updated_at
    )
    VALUES (
        :id, 'user', :user_id, :provider, :name,
        :api_key_encrypted, :api_base, NULL, true,
        now(), now()
    )
    """
)

_INSERT_GATEWAY_MODEL = text(
    """
    INSERT INTO gateway_models (
        id, team_id, name, capability, real_model,
        credential_id, provider, weight, rpm_limit, tpm_limit,
        enabled, tags, last_test_status, last_tested_at, last_test_reason,
        created_at, updated_at
    )
    VALUES (
        :id, :team_id, :name, :capability, :real_model,
        :credential_id, :provider, 1, NULL, NULL,
        :enabled, CAST(:tags AS JSONB), :last_test_status, :last_tested_at, :last_test_reason,
        now(), now()
    )
    """
)


def upgrade() -> None:
    bind = op.get_bind()

    # 1) 为所有有 user_models 的用户补齐 personal team / member（集合化、无锁）
    bind.execute(_UPSERT_PERSONAL_TEAMS)
    bind.execute(_UPSERT_PERSONAL_MEMBERS)

    # 2) 一次性读出所有需要的快照（同事务、同连接，不会自死锁）
    user_models = [dict(r._mapping) for r in bind.execute(_SELECT_USER_MODELS).mappings()]
    if not user_models:
        return

    team_map: dict[uuid.UUID, uuid.UUID] = {
        row["owner_user_id"]: row["id"]
        for row in bind.execute(_SELECT_PERSONAL_TEAM_MAP).mappings()
    }

    existing_by_team_dn: set[tuple[uuid.UUID, str, str]] = set()
    used_names_by_team: dict[uuid.UUID, set[str]] = {}
    for row in bind.execute(_SELECT_EXISTING_PERSONAL_MODELS).mappings():
        tid = row["team_id"]
        existing_by_team_dn.add((tid, str(row["display_name"]), str(row["provider"])))
        used_names_by_team.setdefault(tid, set()).add(str(row["name"]))

    migrated = 0
    skipped_no_key = 0
    skipped_dup = 0

    for um in user_models:
        user_id: uuid.UUID = um["user_id"]
        team_id = team_map.get(user_id)
        if team_id is None:
            # 理论上 step 1 之后必有；防御性跳过
            continue

        display_name = str(um["display_name"])
        provider = str(um["provider"])
        if (team_id, display_name, provider) in existing_by_team_dn:
            skipped_dup += 1
            continue
        if not um.get("api_key_encrypted"):
            skipped_no_key += 1
            continue

        cred_id = uuid.uuid4()
        bind.execute(
            _INSERT_CREDENTIAL,
            {
                "id": cred_id,
                "user_id": user_id,
                "provider": provider,
                "name": f"migrated-{provider}-{str(um['id'])[:8]}",
                "api_key_encrypted": um["api_key_encrypted"],
                "api_base": um.get("api_base"),
            },
        )

        model_types = list(um.get("model_types") or ["text"])
        config = um.get("config") if isinstance(um.get("config"), dict) else None

        for idx, mtype in enumerate(model_types):
            alias = _personal_model_alias(display_name, mtype, suffix=idx if idx else 0)
            used = used_names_by_team.setdefault(team_id, set())
            suffix = 0
            while alias in used:
                suffix += 1
                alias = _personal_model_alias(display_name, mtype, suffix=suffix)
            used.add(alias)

            tags: dict[str, Any] = _tags_for_type(mtype)
            tags["display_name"] = display_name
            if config:
                for k, v in config.items():
                    if v is not None:
                        tags[k] = v

            bind.execute(
                _INSERT_GATEWAY_MODEL,
                {
                    "id": uuid.uuid4(),
                    "team_id": team_id,
                    "name": alias,
                    "capability": _capability_for_type(mtype),
                    "real_model": _litellm_model_id(provider, str(um["model_id"])),
                    "credential_id": cred_id,
                    "provider": provider,
                    "enabled": bool(um.get("is_active", True)),
                    "tags": json.dumps(tags),
                    "last_test_status": um.get("last_test_status"),
                    "last_tested_at": um.get("last_tested_at"),
                    "last_test_reason": um.get("last_test_reason"),
                },
            )
            migrated += 1

        existing_by_team_dn.add((team_id, display_name, provider))

    op.execute(
        text(
            "DO $$ BEGIN RAISE NOTICE "
            "'user_models migration: source=% migrated_rows=% skipped_dup=% skipped_no_key=%', "
            f"{len(user_models)}, {migrated}, {skipped_dup}, {skipped_no_key}; END $$;"
        )
    )


def downgrade() -> None:
    """数据迁移不可逆：gateway_models 行与 user 凭据需人工回滚。"""
