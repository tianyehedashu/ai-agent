"""vision_image_url 策略单元测试。"""

import pytest

from domains.gateway.domain.policies.vision_image_url import (
    parse_listing_studio_image_filename,
    should_inline_vision_image_url,
)


@pytest.mark.unit
class TestParseListingStudioImageFilename:
    def test_relative_path(self) -> None:
        assert (
            parse_listing_studio_image_filename(
                "/api/v1/listing-studio/images/a89f0279441f412495fd4be46670c7b6.jpg"
            )
            == "a89f0279441f412495fd4be46670c7b6.jpg"
        )

    def test_root_path_prefixed(self) -> None:
        assert (
            parse_listing_studio_image_filename(
                "/ai-agent/api/v1/listing-studio/images/bccde334.jpg"
            )
            == "bccde334.jpg"
        )

    def test_absolute_localhost(self) -> None:
        assert (
            parse_listing_studio_image_filename(
                "http://127.0.0.1:8000/ai-agent/api/v1/listing-studio/images/x.png"
            )
            == "x.png"
        )

    def test_rejects_traversal(self) -> None:
        assert parse_listing_studio_image_filename("/api/v1/listing-studio/images/../x.jpg") is None

    def test_external_https(self) -> None:
        assert parse_listing_studio_image_filename("https://cdn.example.com/photo.jpg") is None


@pytest.mark.unit
class TestShouldInlineVisionImageUrl:
    def test_data_url(self) -> None:
        assert not should_inline_vision_image_url("data:image/png;base64,abc")

    def test_relative(self) -> None:
        assert should_inline_vision_image_url("/api/v1/listing-studio/images/a.jpg")

    def test_listing_studio_absolute(self) -> None:
        assert should_inline_vision_image_url(
            "http://localhost/ai-agent/api/v1/listing-studio/images/a.jpg"
        )

    def test_public_cdn(self) -> None:
        assert not should_inline_vision_image_url("https://cdn.example.com/a.jpg")
