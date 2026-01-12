"""
Token 工具测试

测试 Token 计数、截断和成本估算功能
"""

import pytest

from utils.tokens import (
    count_messages_tokens,
    count_tokens,
    estimate_cost,
    truncate_to_token_limit,
)


class TestCountTokens:
    """Token 计数测试"""

    def test_count_empty_string_returns_zero(self):
        """空字符串应返回 0"""
        result = count_tokens("")
        assert result == 0

    def test_count_simple_text(self):
        """简单文本计数"""
        result = count_tokens("Hello world")
        assert result > 0
        assert result <= 5  # "Hello world" 大约 2-3 个 token

    def test_count_chinese_text(self):
        """中文文本计数"""
        result = count_tokens("你好世界")
        assert result > 0

    def test_count_with_different_model(self):
        """不同模型的计数"""
        text = "Hello world"
        result_gpt4 = count_tokens(text, model="gpt-4")
        result_gpt35 = count_tokens(text, model="gpt-3.5-turbo")

        # 不同模型可能有不同的 token 数，但都应该 > 0
        assert result_gpt4 >= 0
        assert result_gpt35 >= 0

    def test_count_long_text(self):
        """长文本计数"""
        long_text = "Hello world " * 100
        result = count_tokens(long_text)
        assert result > 100  # 应该有很多 token


class TestCountMessagesTokens:
    """消息列表 Token 计数测试"""

    def test_count_empty_messages_returns_base_tokens(self):
        """空消息列表返回基础 token"""
        result = count_messages_tokens([])
        assert result == 2  # 回复开始的额外 token

    def test_count_single_message(self):
        """单条消息计数"""
        messages = [{"role": "user", "content": "Hello"}]
        result = count_messages_tokens(messages)
        assert result > 0
        # 至少包含: 4 (消息格式) + content tokens + 2 (回复开始)
        assert result >= 6

    def test_count_multiple_messages(self):
        """多条消息计数"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = count_messages_tokens(messages)
        assert result > 0
        # 每条消息有 4 个额外 token
        assert result >= 10

    def test_count_messages_with_tool_calls(self):
        """包含工具调用的消息计数"""
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"name": "read_file", "arguments": '{"path": "/tmp/test.txt"}'}],
            },
        ]
        result = count_messages_tokens(messages)
        assert result > 0


class TestTruncateToTokenLimit:
    """Token 截断测试"""

    def test_truncate_empty_string(self):
        """空字符串截断"""
        result = truncate_to_token_limit("", max_tokens=10)
        assert result == ""

    def test_truncate_short_text_no_change(self):
        """短文本不截断"""
        text = "Hello world"
        result = truncate_to_token_limit(text, max_tokens=100)
        assert result == text

    def test_truncate_long_text(self):
        """长文本截断"""
        long_text = "Hello world " * 100
        result = truncate_to_token_limit(long_text, max_tokens=10)
        assert len(result) < len(long_text)
        # 截断后的 token 数应该 <= max_tokens
        assert count_tokens(result) <= 10

    def test_truncate_preserves_beginning(self):
        """截断保留开头部分"""
        text = "First part. Second part. Third part."
        result = truncate_to_token_limit(text, max_tokens=5)
        # 应该保留开头
        assert result.startswith("First")


class TestEstimateCost:
    """成本估算测试"""

    def test_estimate_cost_gpt4(self):
        """GPT-4 成本估算"""
        cost = estimate_cost(input_tokens=1000, output_tokens=500, model="gpt-4")
        # 输入: 1000 * 0.03 / 1000 = 0.03
        # 输出: 500 * 0.06 / 1000 = 0.03
        # 总计: 0.06
        assert cost == pytest.approx(0.06, abs=0.01)

    def test_estimate_cost_gpt35(self):
        """GPT-3.5 成本估算"""
        cost = estimate_cost(
            input_tokens=1000, output_tokens=500, model="gpt-3.5-turbo"
        )
        # 输入: 1000 * 0.0015 / 1000 = 0.0015
        # 输出: 500 * 0.002 / 1000 = 0.001
        # 总计: 0.0025
        assert cost == pytest.approx(0.0025, abs=0.001)

    def test_estimate_cost_zero_tokens(self):
        """零 token 成本为 0"""
        cost = estimate_cost(input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_estimate_cost_unknown_model_uses_default(self):
        """未知模型使用默认定价"""
        cost = estimate_cost(
            input_tokens=1000, output_tokens=500, model="unknown-model"
        )
        # 应该使用 GPT-4 定价
        assert cost > 0
