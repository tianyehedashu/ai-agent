"""upstream_catalog_capability_prep 单测。"""

from __future__ import annotations

from domains.gateway.application.upstream_catalog_capability_prep import (
    prepare_gateway_write_from_upstream_catalog,
    should_apply_catalog_prep_to_base_tags,
)
from domains.gateway.domain.litellm_capability_mapping import LitellmModelInfoHints


class _FakeHint:
    def __init__(self, hints: LitellmModelInfoHints | None) -> None:
        self._hints = hints

    def get_model_hints(self, *, provider: str, real_model: str) -> LitellmModelInfoHints | None:
        _ = provider, real_model
        return self._hints

    def supports_reasoning(self, *, provider: str, real_model: str) -> bool | None:
        hints = self.get_model_hints(provider=provider, real_model=real_model)
        if hints is None:
            return None
        value = hints.get("supports_reasoning")
        return value if isinstance(value, bool) else None


def test_prepare_infers_vision_from_model_id_regex() -> None:
    cap, tags = prepare_gateway_write_from_upstream_catalog(
        provider="openai",
        upstream_id="kimi-k2.6",
        owned_by=None,
        api_base=None,
        base_tags=None,
        capability_override="chat",
    )
    assert cap == "chat"
    assert tags.get("supports_vision") is True


def test_prepare_image_gen_capability() -> None:
    cap, tags = prepare_gateway_write_from_upstream_catalog(
        provider="openai",
        upstream_id="dall-e-3",
        owned_by=None,
        api_base=None,
        base_tags=None,
        capability_override=None,
    )
    assert cap == "image"
    assert tags.get("supports_image_gen") is True


def test_capability_override_incompatible_falls_back_to_inferred() -> None:
    cap, tags = prepare_gateway_write_from_upstream_catalog(
        provider="openai",
        upstream_id="dall-e-3",
        owned_by=None,
        api_base=None,
        base_tags=None,
        capability_override="chat",
    )
    assert cap == "image"
    assert tags.get("supports_image_gen") is True


def test_should_apply_catalog_prep_when_tags_empty() -> None:
    assert should_apply_catalog_prep_to_base_tags(None) is True
    assert should_apply_catalog_prep_to_base_tags({}) is True
    assert should_apply_catalog_prep_to_base_tags({"display_name": "x"}) is True


def test_should_not_apply_when_capability_tags_present() -> None:
    assert should_apply_catalog_prep_to_base_tags({"supports_vision": True}) is False


def test_prepare_unions_litellm_vision_with_regex() -> None:
    from domains.gateway.application.upstream_model_types_for_catalog import (
        infer_upstream_model_types_for_catalog,
    )

    types = infer_upstream_model_types_for_catalog(
        "volcengine",
        "doubao-seed-2-0-lite-260215",
        hint_port=_FakeHint({"supports_vision": True}),
    )
    assert "text" in types
    assert "image" in types


def test_prepare_gateway_model_write_infers_image_capability_for_dalle() -> None:
    from domains.gateway.application.management.write_modules.model_writes import (
        _prepare_gateway_model_write_fields,
    )

    prepared = _prepare_gateway_model_write_fields(
        provider="openai",
        real_model="dall-e-3",
        tags=None,
        credential_provider="openai",
    )
    assert prepared.catalog_capability == "image"
    assert prepared.enriched_tags.get("supports_image_gen") is True


def test_prepare_embedding_capability_from_model_id() -> None:
    cap, tags = prepare_gateway_write_from_upstream_catalog(
        provider="openai",
        upstream_id="text-embedding-3-small",
        owned_by=None,
        api_base=None,
        base_tags=None,
        capability_override="chat",
    )
    assert cap == "embedding"
    assert tags == {}


def test_infer_non_personal_gateway_capability() -> None:
    from domains.gateway.domain.upstream_type_inference import (
        infer_non_personal_gateway_capability,
    )

    assert infer_non_personal_gateway_capability("text-embedding-3-small") == "embedding"
    assert infer_non_personal_gateway_capability("gpt-4o") is None
