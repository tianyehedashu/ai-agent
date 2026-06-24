"""把「按 OpenAI 自定义 base 导入的 Agnes 端点」迁移到一等公民 ``agnes`` provider。

背景：Agnes（apihub.agnes-ai.com）是 OpenAI 伪兼容端点，图生图须用字面量
``extra_body``，须经 ``provider=agnes`` 的直连分支才能正确出站（见
``domains/gateway/domain/policies/agnes_image``）。早期用户「改 OpenAI base URL」
导入的记录 ``provider`` 仍是 ``openai`` / ``custom``，且常被错分为 chat 模型。

本脚本（幂等）按 api_base 主机名识别 Agnes 凭据，并：
- 凭据：``provider`` → ``agnes``，``profile_id`` → ``agnes.default``（api_base 保持不变）；
- 绑定模型：``provider`` → ``agnes``，按上游 id 重新推断 ``capability``（生图 → ``image``）
  并同步 ``real_model`` 去前缀、``supports_*`` 能力 tags。

冲突保护：若目标租户/用户已存在同名 ``agnes`` 凭据（唯一约束），跳过该凭据及其模型。

用法：
    # 预览（默认不写库）
    uv run python -m scripts.migrate_agnes_provider
    # 实际执行
    uv run python -m scripts.migrate_agnes_provider --apply
    # 自定义识别主机名（默认 apihub.agnes-ai.com）
    uv run python -m scripts.migrate_agnes_provider --host apihub.agnes-ai.com --apply
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select

from domains.gateway.domain.litellm_model_id import is_openai_official_endpoint
from domains.gateway.domain.model_types_tags import (
    primary_capability_from_model_types,
    tags_from_model_types,
)
from domains.gateway.domain.policies.agnes_image import AGNES_PROVIDER
from domains.gateway.domain.upstream_endpoint import credential_api_base
from domains.gateway.domain.upstream_profile import default_profile_id
from domains.gateway.domain.upstream_type_inference import (
    filter_valid_personal_model_types,
    infer_upstream_model_types,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from libs.db.database import get_db_session

_MIGRATABLE_PROVIDERS = ("openai", "custom")
_AGNES_PROFILE_ID = default_profile_id(AGNES_PROVIDER)


def _host_of(api_base: str | None) -> str | None:
    if not api_base:
        return None
    netloc = urlparse(api_base.strip()).netloc.lower()
    return netloc or None


def _strip_openai_prefix(real_model: str) -> str:
    s = real_model.strip()
    return s.split("/", 1)[1] if s.lower().startswith("openai/") else s


def _scope_key(cred: ProviderCredential) -> tuple[Any, ...]:
    """凭据唯一性作用域键（与 ProviderCredential 唯一约束对齐）。"""
    if cred.tenant_id is not None:
        return ("tenant", cred.tenant_id)
    return ("user", cred.scope, cred.scope_id)


async def _existing_agnes_credential_names(
    session, cred: ProviderCredential
) -> set[str]:
    """目标作用域下已存在的 ``agnes`` 凭据名（唯一约束冲突检测）。"""
    stmt = select(ProviderCredential.name).where(
        ProviderCredential.provider == AGNES_PROVIDER
    )
    if cred.tenant_id is not None:
        stmt = stmt.where(ProviderCredential.tenant_id == cred.tenant_id)
    else:
        stmt = stmt.where(
            ProviderCredential.scope == cred.scope,
            ProviderCredential.scope_id == cred.scope_id,
        )
    rows = await session.execute(stmt)
    return {name for (name,) in rows.all()}


async def migrate_agnes_provider(*, host: str, apply: bool) -> None:
    async with get_db_session() as session:
        # 仅按 provider 取候选，host 命中纯 Python 精筛：``credential_api_base``
        # 会合并 legacy ``api_base`` 与 ``api_bases.openai_compat``，故不在 SQL 层
        # 用 ``api_base.ilike`` 粗筛，避免漏掉只存于 ``api_bases`` JSON 的记录。
        stmt = select(ProviderCredential).where(
            ProviderCredential.provider.in_(_MIGRATABLE_PROVIDERS)
        )
        candidates = [
            c
            for c in (await session.execute(stmt)).scalars().all()
            if _host_of(credential_api_base(c)) == host
            and not is_openai_official_endpoint(credential_api_base(c))
        ]

        if not candidates:
            print(f"未发现指向 {host} 的 openai/custom 凭据，无需迁移。")
            return

        print(f"发现 {len(candidates)} 条候选 Agnes 凭据（host={host}）：\n")
        migrated_creds = 0
        migrated_models = 0
        # 每个作用域已占用的 agnes 凭据名：DB 既有 + 本次已迁移，避免本批次互相撞名
        # （dry-run 不写库时尤其不能依赖 autoflush）。
        taken_by_scope: dict[tuple[Any, ...], set[str]] = {}

        for cred in candidates:
            scope_desc = (
                f"tenant={cred.tenant_id}"
                if cred.tenant_id is not None
                else f"{cred.scope}:{cred.scope_id}"
            )
            key = _scope_key(cred)
            if key not in taken_by_scope:
                taken_by_scope[key] = await _existing_agnes_credential_names(
                    session, cred
                )
            taken = taken_by_scope[key]
            if cred.name in taken:
                print(
                    f"  [SKIP] 凭据 {cred.id} ({cred.name}, {scope_desc})："
                    f"目标作用域已存在同名 agnes 凭据，跳过其及绑定模型。"
                )
                continue

            print(
                f"  [CRED] {cred.id} ({cred.name}, {scope_desc}) "
                f"provider {cred.provider}->{AGNES_PROVIDER}, "
                f"profile_id {cred.profile_id!r}->{_AGNES_PROFILE_ID!r}"
            )
            if apply:
                cred.provider = AGNES_PROVIDER
                cred.profile_id = _AGNES_PROFILE_ID
            taken.add(cred.name)
            migrated_creds += 1

            models = (
                (
                    await session.execute(
                        select(GatewayModel).where(GatewayModel.credential_id == cred.id)
                    )
                )
                .scalars()
                .all()
            )
            for m in models:
                new_real = _strip_openai_prefix(m.real_model)
                inferred = filter_valid_personal_model_types(
                    infer_upstream_model_types(AGNES_PROVIDER, new_real)
                )
                new_cap = (
                    primary_capability_from_model_types(inferred) if inferred else m.capability
                )
                changes = []
                if m.provider != AGNES_PROVIDER:
                    changes.append(f"provider {m.provider}->{AGNES_PROVIDER}")
                if new_cap != m.capability:
                    changes.append(f"capability {m.capability}->{new_cap}")
                if new_real != m.real_model:
                    changes.append(f"real_model {m.real_model!r}->{new_real!r}")
                print(
                    f"      [MODEL] {m.id} ({m.name}) "
                    + ("; ".join(changes) if changes else "无字段变更（仅归属凭据）")
                )
                if apply:
                    m.provider = AGNES_PROVIDER
                    m.real_model = new_real
                    m.capability = new_cap
                    if inferred:
                        m.tags = tags_from_model_types(
                            list(inferred),
                            existing_tags=m.tags or {},
                            capability=new_cap,
                            clear_unselected=False,
                        )
                migrated_models += 1

        if apply:
            await session.commit()
            print(
                f"\n完成：已迁移 {migrated_creds} 条凭据 / {migrated_models} 个模型。"
                "\n注意：网关 Router 缓存了 deployment，请重启网关进程或等待缓存 TTL 后生效。"
            )
        else:
            print(
                f"\n[DRY-RUN] 将迁移 {migrated_creds} 条凭据 / {migrated_models} 个模型。"
                "\n加 --apply 实际写库。"
            )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host",
        default="apihub.agnes-ai.com",
        help="按 api_base 主机名识别 Agnes 凭据（默认 apihub.agnes-ai.com）",
    )
    parser.add_argument("--apply", action="store_true", help="实际写库（默认仅预览）")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(migrate_agnes_provider(host=args.host, apply=args.apply))
