"""诊断指定团队模型的 Router deployment 状态。

用法:
    cd backend && uv run python scripts/diagnose_router_deployment.py
    cd backend && uv run python scripts/diagnose_router_deployment.py --call
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

TEAM_ID = uuid.UUID("409c3f0d-2b98-4a30-8826-e2cbf5eaca65")
MODEL_NAME = "kimi-for-coding-chat"


async def main() -> None:
    from domains.gateway.domain.route.router_model_name import encode_router_model_name
    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
    from domains.gateway.infrastructure.litellm.router_singleton import (
        _build_deployments_for_encoded_model,
        _build_router_kwargs,
        get_router_sync,
        router_deployment_model_names,
    )
    from domains.tenancy.infrastructure.models.team import Team
    from libs.db.database import get_db_session, init_db

    encoded = encode_router_model_name(TEAM_ID, MODEL_NAME)
    await init_db()
    async with get_db_session() as session:
        team = await session.get(Team, TEAM_ID)
        print("=== TEAM ===")
        print(f"id={TEAM_ID} name={getattr(team, 'name', None)} kind={getattr(team, 'kind', None)}")

        rows = list(
            (
                await session.execute(
                    select(GatewayModel).where(
                        GatewayModel.tenant_id == TEAM_ID,
                        GatewayModel.name == MODEL_NAME,
                    )
                )
            ).scalars().all()
        )
        print(f"\n=== GatewayModel name={MODEL_NAME} count={len(rows)} ===")
        for model in rows:
            print(
                f"  id={model.id} enabled={model.enabled} provider={model.provider} "
                f"real_model={model.real_model}"
            )
            print(
                f"  credential_id={model.credential_id} capability={model.capability} "
                f"upstream_call_shape={model.upstream_call_shape}"
            )
            print(
                f"  last_test_status={model.last_test_status} "
                f"last_test_reason={model.last_test_reason}"
            )

        routes = list(
            (
                await session.execute(
                    select(GatewayRoute).where(
                        GatewayRoute.tenant_id == TEAM_ID,
                        GatewayRoute.virtual_model == MODEL_NAME,
                    )
                )
            ).scalars().all()
        )
        print(f"\n=== GatewayRoute virtual_model={MODEL_NAME} count={len(routes)} ===")
        for route in routes:
            print(
                f"  id={route.id} enabled={route.enabled} "
                f"primary_models={route.primary_models} strategy={route.strategy}"
            )

        kimi_models = list(
            (
                await session.execute(
                    select(GatewayModel).where(
                        GatewayModel.tenant_id == TEAM_ID,
                        GatewayModel.name.ilike("%kimi%"),
                    )
                )
            ).scalars().all()
        )
        print(f"\n=== All team models with kimi in name ({len(kimi_models)}) ===")
        for model in kimi_models:
            print(
                f"  name={model.name} enabled={model.enabled} cred={model.credential_id} "
                f"test={model.last_test_status}"
            )

        cred_ids: set[uuid.UUID] = {model.credential_id for model in rows}
        for route in routes:
            for primary_name in route.primary_models or ():
                primary = (
                    await session.execute(
                        select(GatewayModel).where(
                            GatewayModel.tenant_id == TEAM_ID,
                            GatewayModel.name == primary_name,
                        )
                    )
                ).scalar_one_or_none()
                if primary is not None:
                    cred_ids.add(primary.credential_id)

        print("\n=== Credentials ===")
        for cred_id in cred_ids:
            cred = await session.get(ProviderCredential, cred_id)
            if cred is None:
                print(f"  id={cred_id} NOT FOUND")
                continue
            print(
                f"  id={cred.id} name={cred.name} provider={cred.provider} "
                f"is_active={cred.is_active} scope={cred.scope}"
            )
            print(f"    tenant_id={cred.tenant_id} api_base={cred.api_base}")

        print(f"\n=== Encoded model: {encoded} ===")
        deployments = await _build_deployments_for_encoded_model(session, encoded)
        print(f"_build_deployments_for_encoded_model count={len(deployments)}")
        for dep in deployments:
            model_info = dep.get("model_info", {})
            litellm_params = dep.get("litellm_params", {})
            print(
                f"  model_name={dep.get('model_name')} "
                f"real={model_info.get('gateway_real_model')} "
                f"provider={model_info.get('gateway_provider')}"
            )
            print(
                f"    litellm model={litellm_params.get('model')} "
                f"has_api_key={bool(litellm_params.get('api_key'))} "
                f"api_base={litellm_params.get('api_base')}"
            )

        router_kwargs = await _build_router_kwargs(session)
        all_names = [
            str(dep.get("model_name"))
            for dep in router_kwargs.get("model_list", [])
            if isinstance(dep, dict) and dep.get("model_name")
        ]
        print(f"\n=== Full router model_list size={len(all_names)} ===")
        print(f"encoded in router: {encoded in all_names}")
        matching = [name for name in all_names if MODEL_NAME in name]
        print(f"models containing {MODEL_NAME}: {matching}")

        router = get_router_sync()
        if router is None:
            print("\n=== In-memory router: None (not initialized in this process) ===")
        else:
            live = router_deployment_model_names(router)
            print(f"\n=== In-memory router deployments={len(live)} ===")
            print(f"encoded in live router: {encoded in live}")

        from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey
        from domains.gateway.infrastructure.models.virtual_key_team_grant import (
            GatewayVirtualKeyTeamGrant,
        )

        vkeys = list(
            (
                await session.execute(
                    select(GatewayVirtualKey).where(GatewayVirtualKey.name.ilike("%test 2%"))
                )
            )
            .scalars()
            .all()
        )
        print(f"\n=== VKeys matching 'test 2' ({len(vkeys)}) ===")
        for vkey in vkeys:
            print(
                f"  id={vkey.id} name={vkey.name} tenant_id={vkey.tenant_id} "
                f"is_active={vkey.is_active}"
            )
            grants = list(
                (
                    await session.execute(
                        select(GatewayVirtualKeyTeamGrant).where(
                            GatewayVirtualKeyTeamGrant.vkey_id == vkey.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            for grant in grants:
                grant_team = await session.get(Team, grant.tenant_id)
                print(
                    f"    grant tenant_id={grant.tenant_id} "
                    f"name={getattr(grant_team, 'name', None)} "
                    f"slug={getattr(grant_team, 'slug', None)}"
                )

        dev_teams = list(
            (await session.execute(select(Team).where(Team.name.ilike("%研发%")))).scalars().all()
        )
        print(f"\n=== Teams matching 研发 ({len(dev_teams)}) ===")
        for dev_team in dev_teams:
            print(
                f"  id={dev_team.id} name={dev_team.name} slug={dev_team.slug} kind={dev_team.kind}"
            )


async def simulate_router_call() -> None:
    from domains.gateway.domain.route.router_model_name import encode_router_model_name
    from domains.gateway.infrastructure.litellm.router_singleton import (
        get_router,
        reload_router,
        router_deployment_model_names,
    )
    from libs.db.database import get_db_session, init_db

    encoded = encode_router_model_name(TEAM_ID, MODEL_NAME)
    await init_db()
    async with get_db_session() as session:
        router = await get_router(session)
        live = router_deployment_model_names(router)
        print(f"\n=== After get_router: deployments={len(live)} encoded_present={encoded in live}")
        if encoded not in live:
            print("encoded missing; forcing reload_router...")
            router = await reload_router(session)
            live = router_deployment_model_names(router)
            print(f"after reload: deployments={len(live)} encoded_present={encoded in live}")

        try:
            result = await router.acompletion(
                model=encoded,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
                temperature=0,
            )
            content = result.choices[0].message.content if result.choices else ""
            print(f"\n=== Router acompletion SUCCESS preview={content[:80]!r} ===")
        except Exception as exc:
            print("\n=== Router acompletion FAILED ===")
            print(f"type={type(exc).__name__}")
            print(f"message={exc}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--call":
        asyncio.run(simulate_router_call())
    else:
        asyncio.run(main())
