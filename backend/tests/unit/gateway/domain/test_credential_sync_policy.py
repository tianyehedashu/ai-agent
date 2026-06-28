"""credential_sync_policy 纯函数测试。"""

from __future__ import annotations

from domains.gateway.domain.credential.credential_sync_policy import resolve_bootstrap_api_base

CODING_BASE = "https://open.bigmodel.cn/api/coding/paas/v4"
DEFAULT_ZHIPU = "https://open.bigmodel.cn/api/paas/v4"


def test_new_credential_uses_env_base() -> None:
    assert (
        resolve_bootstrap_api_base(
            provider="zhipuai",
            env_base=CODING_BASE,
            existing_base=None,
            is_new_credential=True,
        )
        == CODING_BASE
    )


def test_new_credential_falls_back_to_default() -> None:
    assert (
        resolve_bootstrap_api_base(
            provider="zhipuai",
            env_base=None,
            existing_base=None,
            is_new_credential=True,
        )
        == DEFAULT_ZHIPU
    )


def test_existing_non_empty_base_preserved_over_env() -> None:
    managed = "https://admin.example.com/v1"
    assert (
        resolve_bootstrap_api_base(
            provider="zhipuai",
            env_base=CODING_BASE,
            existing_base=managed,
            is_new_credential=False,
        )
        == managed
    )


def test_existing_empty_base_backfilled_from_env() -> None:
    assert (
        resolve_bootstrap_api_base(
            provider="zhipuai",
            env_base=CODING_BASE,
            existing_base=None,
            is_new_credential=False,
        )
        == CODING_BASE
    )


def test_force_env_sync_overwrites_existing() -> None:
    assert (
        resolve_bootstrap_api_base(
            provider="zhipuai",
            env_base=CODING_BASE,
            existing_base="https://old.example.com/v1",
            is_new_credential=False,
            force_env_sync=True,
        )
        == CODING_BASE
    )
