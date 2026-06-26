"""non_token_cost 领域策略单元测试。"""

from dataclasses import dataclass
from decimal import Decimal

from domains.gateway.domain.policies.non_token_cost import (
    capability_default_billing_mode,
    estimate_non_token_cost_from_extra,
    merge_non_token_extra_from_litellm,
    response_image_count,
)
from domains.gateway.domain.types import GatewayCapability


def test_capability_default_billing_mode() -> None:
    assert capability_default_billing_mode(GatewayCapability.CHAT.value) == "token"
    assert capability_default_billing_mode(GatewayCapability.AUDIO_SPEECH.value) == "per_request"
    assert capability_default_billing_mode(GatewayCapability.IMAGE.value) == "hybrid"
    assert capability_default_billing_mode(GatewayCapability.EMBEDDING.value) == "token"


def test_merge_non_token_extra_from_litellm() -> None:
    entry = {
        "input_cost_per_token": 1e-6,
        "input_cost_per_image": 0.04,
        "output_cost_per_second": 0.0001,
        "ignored_key": 99,
    }
    extra = merge_non_token_extra_from_litellm(entry)
    assert extra == {"input_cost_per_image": 0.04, "output_cost_per_second": 0.0001}


def test_estimate_non_token_cost_from_extra_image() -> None:
    response = {
        "data": [{"url": "https://example.com/a.png"}, {"url": "https://example.com/b.png"}]
    }
    cost = estimate_non_token_cost_from_extra(
        {"input_cost_per_image": 0.02},
        response,
    )
    assert cost == Decimal("0.04")


def test_estimate_non_token_cost_from_extra_returns_none_when_unmeasurable() -> None:
    cost = estimate_non_token_cost_from_extra(
        {"input_cost_per_image": 0.02},
        None,
    )
    assert cost is None


# ---------------------------------------------------------------------------
# response_image_count —— 从响应中提取生成的图片张数
# ---------------------------------------------------------------------------


@dataclass
class _FakeResponse:
    """模拟 OpenAI 风格响应对象（带 ``data`` 属性）。"""

    data: object | None = None


def test_response_image_count_none_response_returns_zero() -> None:
    assert response_image_count(None) == 0


def test_response_image_count_dict_with_list_data_returns_length() -> None:
    response = {"data": [{"url": "a"}, {"url": "b"}, {"url": "c"}]}
    assert response_image_count(response) == 3


def test_response_image_count_dict_with_empty_list_returns_zero() -> None:
    assert response_image_count({"data": []}) == 0


def test_response_image_count_dict_with_single_object_data_returns_one() -> None:
    """``data`` 非数组但非空时按 1 张计（兼容单对象响应）。"""
    assert response_image_count({"data": {"url": "a"}}) == 1


def test_response_image_count_dict_without_data_key_returns_zero() -> None:
    assert response_image_count({"other": "value"}) == 0


def test_response_image_count_object_with_data_attribute_returns_length() -> None:
    """对象属性访问路径：``getattr(response, "data", None)``。"""
    response = _FakeResponse(data=[{"url": "a"}, {"url": "b"}])
    assert response_image_count(response) == 2


def test_response_image_count_object_with_none_data_returns_zero() -> None:
    response = _FakeResponse(data=None)
    assert response_image_count(response) == 0


def test_response_image_count_object_without_data_attribute_returns_zero() -> None:
    @dataclass
    class _NoData:
        value: int = 42

    assert response_image_count(_NoData()) == 0
