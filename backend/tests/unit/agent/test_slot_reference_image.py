"""slot_reference_image 单元测试"""

from domains.agent.domain.listing_studio.slot_reference_image import (
    extract_global_source_reference,
    normalize_explicit_reference_url,
    resolve_product_source_image_url,
    resolve_slot_reference_image,
)


class TestResolveProductSourceImageUrl:
    def test_manual_priority(self) -> None:
        assert (
            resolve_product_source_image_url(
                "https://manual.jpg",
                ["https://input.jpg"],
            )
            == "https://manual.jpg"
        )

    def test_falls_back_to_input(self) -> None:
        assert (
            resolve_product_source_image_url(None, ["https://input.jpg"])
            == "https://input.jpg"
        )

    def test_empty_returns_none(self) -> None:
        assert resolve_product_source_image_url(None, []) is None


class TestResolveSlotReferenceImage:
    def test_explicit_wins(self) -> None:
        assert (
            resolve_slot_reference_image(
                mode="current",
                slot=2,
                explicit_reference_url="https://explicit.jpg",
                current_slot_url="https://current.jpg",
            )
            == "https://explicit.jpg"
        )

    def test_current_mode_uses_slot_image(self) -> None:
        assert (
            resolve_slot_reference_image(
                mode="current",
                slot=3,
                current_slot_url="https://gen3.jpg",
                source_image_url="https://source.jpg",
            )
            == "https://gen3.jpg"
        )

    def test_current_mode_falls_back_to_source(self) -> None:
        assert (
            resolve_slot_reference_image(
                mode="current",
                slot=3,
                source_image_url="https://source.jpg",
            )
            == "https://source.jpg"
        )

    def test_source_mode(self) -> None:
        assert (
            resolve_slot_reference_image(
                mode="source",
                slot=1,
                current_slot_url="https://gen1.jpg",
                source_image_url="https://source.jpg",
            )
            == "https://source.jpg"
        )

    def test_chain_slot1_uses_source(self) -> None:
        assert (
            resolve_slot_reference_image(
                mode="chain",
                slot=1,
                source_image_url="https://source.jpg",
                slot1_generated_url="https://white.jpg",
            )
            == "https://source.jpg"
        )

    def test_chain_slot2_uses_slot1(self) -> None:
        assert (
            resolve_slot_reference_image(
                mode="chain",
                slot=2,
                source_image_url="https://source.jpg",
                slot1_generated_url="https://white.jpg",
            )
            == "https://white.jpg"
        )

    def test_chain_slot2_falls_back_source_when_no_slot1(self) -> None:
        assert (
            resolve_slot_reference_image(
                mode="chain",
                slot=5,
                source_image_url="https://source.jpg",
            )
            == "https://source.jpg"
        )


class TestNormalizeExplicitReferenceUrl:
    def test_single_slot_keeps_explicit(self) -> None:
        assert (
            normalize_explicit_reference_url(
                slot=3,
                explicit_reference_url="https://current.jpg",
                global_source_reference_url="https://current.jpg",
                prompt_count=1,
            )
            == "https://current.jpg"
        )

    def test_batch_clears_merged_duplicate_for_slot2(self) -> None:
        assert (
            normalize_explicit_reference_url(
                slot=2,
                explicit_reference_url="https://source.jpg",
                global_source_reference_url="https://source.jpg",
                prompt_count=8,
            )
            is None
        )

    def test_batch_keeps_distinct_explicit(self) -> None:
        assert (
            normalize_explicit_reference_url(
                slot=2,
                explicit_reference_url="https://custom.jpg",
                global_source_reference_url="https://source.jpg",
                prompt_count=8,
            )
            == "https://custom.jpg"
        )


class TestExtractGlobalSourceReference:
    def test_first_non_empty_wins(self) -> None:
        prompts = [
            {"slot": 2, "prompt": "b"},
            {"slot": 1, "prompt": "a", "reference_image_url": "https://source.jpg"},
        ]
        assert extract_global_source_reference(prompts) == "https://source.jpg"
