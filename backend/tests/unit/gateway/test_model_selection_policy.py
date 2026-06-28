"""model_selection_policy 单元测试"""

import pytest

from domains.gateway.domain.catalog.model_selection_policy import pick_configured_or_first_visible


@pytest.mark.unit
class TestPickConfiguredOrFirstVisible:
    def test_configured_in_visible(self) -> None:
        visible = frozenset({"deepseek/deepseek-chat", "dashscope/qwen-turbo"})
        assert (
            pick_configured_or_first_visible("deepseek/deepseek-chat", visible)
            == "deepseek/deepseek-chat"
        )

    def test_configured_not_in_visible_falls_back_to_first_sorted(self) -> None:
        visible = frozenset({"zai/glm-4-flash", "deepseek/deepseek-chat"})
        assert (
            pick_configured_or_first_visible("dashscope/qwen-vl-max", visible)
            == "deepseek/deepseek-chat"
        )

    def test_empty_visible_returns_none(self) -> None:
        assert pick_configured_or_first_visible("deepseek/deepseek-chat", frozenset()) is None

    def test_whitespace_configured_stripped(self) -> None:
        visible = frozenset({"a/model"})
        assert pick_configured_or_first_visible("  a/model  ", visible) == "a/model"
