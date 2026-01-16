"""
Token Utilities 单元测试
"""

import pytest

from utils.tokens import (
    count_messages_tokens,
    count_tokens,
    estimate_cost,
    truncate_to_token_limit,
)


@pytest.mark.unit
class TestTokens:
    """Token 计算工具测试"""

    def test_count_tokens(self):
        """测试: 计算文本 Token 数量"""
        # Arrange
        text = "Hello, world!"

        # Act
        count = count_tokens(text)

        # Assert
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_empty(self):
        """测试: 计算空文本 Token 数量"""
        # Arrange
        text = ""

        # Act
        count = count_tokens(text)

        # Assert
        assert count == 0

    def test_count_tokens_different_models(self):
        """测试: 不同模型的 Token 计算"""
        # Arrange
        text = "Hello, world!"

        # Act
        count_gpt4 = count_tokens(text, model="gpt-4")
        count_gpt35 = count_tokens(text, model="gpt-3.5-turbo")

        # Assert
        assert count_gpt4 > 0
        assert count_gpt35 > 0

    def test_count_tokens_unicode(self):
        """测试: Unicode 字符的 Token 计算"""
        # Arrange
        text = "你好，世界！"

        # Act
        count = count_tokens(text)

        # Assert
        assert count > 0

    def test_count_tokens_fallback_encoding(self):
        """测试: 未知模型回退到默认编码"""
        # Arrange
        text = "Test text"
        unknown_model = "unknown-model-xyz"

        # Act
        count = count_tokens(text, model=unknown_model)

        # Assert
        assert count > 0  # 应该使用 cl100k_base 编码

    def test_count_messages_tokens(self):
        """测试: 计算消息列表 Token 数量"""
        # Arrange
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        # Act
        count = count_messages_tokens(messages)

        # Assert
        assert count > 0
        # 应该包含消息格式的额外 Token
        assert count > count_tokens("Hello") + count_tokens("Hi there")

    def test_count_messages_tokens_empty(self):
        """测试: 计算空消息列表 Token 数量"""
        # Arrange
        messages = []

        # Act
        count = count_messages_tokens(messages)

        # Assert
        assert count == 2  # 只有回复开始的额外 Token

    def test_count_messages_tokens_with_list(self):
        """测试: 计算包含列表的消息 Token 数量"""
        # Arrange
        messages = [
            {
                "role": "assistant",
                "content": "Here are the results:",
                "tool_calls": [{"name": "read_file", "arguments": {"path": "/tmp/test.txt"}}],
            }
        ]

        # Act
        count = count_messages_tokens(messages)

        # Assert
        assert count > 0

    def test_truncate_to_token_limit_short_text(self):
        """测试: 截断短文本（不需要截断）"""
        # Arrange
        text = "Short text"
        max_tokens = 100

        # Act
        result = truncate_to_token_limit(text, max_tokens)

        # Assert
        assert result == text

    def test_truncate_to_token_limit_long_text(self):
        """测试: 截断长文本"""
        # Arrange
        text = "This is a very long text. " * 100
        max_tokens = 10

        # Act
        result = truncate_to_token_limit(text, max_tokens)

        # Assert
        assert len(result) < len(text)
        assert count_tokens(result) <= max_tokens

    def test_truncate_to_token_limit_exact_length(self):
        """测试: 截断到精确长度"""
        # Arrange
        text = "This is a test text"
        max_tokens = count_tokens(text)

        # Act
        result = truncate_to_token_limit(text, max_tokens)

        # Assert
        assert count_tokens(result) <= max_tokens

    def test_estimate_cost_gpt4(self):
        """测试: 估算 GPT-4 成本"""
        # Arrange
        input_tokens = 1000
        output_tokens = 500

        # Act
        cost = estimate_cost(input_tokens, output_tokens, model="gpt-4")

        # Assert
        assert cost > 0
        # GPT-4: input $0.03/1K, output $0.06/1K
        expected = (1000 / 1000) * 0.03 + (500 / 1000) * 0.06
        assert abs(cost - expected) < 0.01

    def test_estimate_cost_gpt35(self):
        """测试: 估算 GPT-3.5 成本"""
        # Arrange
        input_tokens = 1000
        output_tokens = 500

        # Act
        cost = estimate_cost(input_tokens, output_tokens, model="gpt-3.5-turbo")

        # Assert
        assert cost > 0
        # GPT-3.5: input $0.0015/1K, output $0.002/1K
        expected = (1000 / 1000) * 0.0015 + (500 / 1000) * 0.002
        assert abs(cost - expected) < 0.01

    def test_estimate_cost_claude(self):
        """测试: 估算 Claude 成本"""
        # Arrange
        input_tokens = 1000
        output_tokens = 500

        # Act
        cost_sonnet = estimate_cost(input_tokens, output_tokens, model="claude-3-sonnet")

        # Assert
        assert cost_sonnet > 0

    def test_estimate_cost_unknown_model(self):
        """测试: 估算未知模型成本（使用默认定价）"""
        # Arrange
        input_tokens = 1000
        output_tokens = 500
        unknown_model = "unknown-model"

        # Act
        cost = estimate_cost(input_tokens, output_tokens, model=unknown_model)

        # Assert
        assert cost > 0  # 应该使用 GPT-4 的默认定价

    def test_estimate_cost_zero_tokens(self):
        """测试: 估算零 Token 成本"""
        # Arrange
        input_tokens = 0
        output_tokens = 0

        # Act
        cost = estimate_cost(input_tokens, output_tokens)

        # Assert
        assert cost == 0.0
