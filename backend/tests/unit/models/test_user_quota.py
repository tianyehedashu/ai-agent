"""
UserQuota 模型单元测试

TDD Cycle 3-4: UserQuota 模型
"""

from datetime import UTC, datetime, timedelta
import uuid

import pytest

# 预先导入所有模型以初始化 SQLAlchemy 注册表
# 这是必要的，因为 User 模型有对 Agent、Session、Memory 的关系引用
from domains.agent.infrastructure.models import Agent, Memory, Session  # noqa: F401
from domains.identity.infrastructure.models.quota import QuotaUsageLog, UserQuota


@pytest.mark.unit
class TestUserQuota:
    """UserQuota 模型测试"""

    def test_create_user_quota(self):
        """测试: 创建用户配额"""
        # Arrange
        user_id = uuid.uuid4()

        # Act
        quota = UserQuota(
            user_id=user_id,
            daily_text_requests=100,
            daily_image_requests=10,
            daily_embedding_requests=50,
            monthly_token_limit=1000000,
        )

        # Assert
        assert quota.user_id == user_id
        assert quota.daily_text_requests == 100
        assert quota.daily_image_requests == 10
        assert quota.daily_embedding_requests == 50
        assert quota.monthly_token_limit == 1000000

    def test_create_user_quota_with_current_usage(self):
        """测试: 创建带当前用量的配额"""
        # Arrange
        user_id = uuid.uuid4()

        # Act
        quota = UserQuota(
            user_id=user_id,
            daily_text_requests=100,
            current_daily_text=25,
            current_daily_image=5,
            current_monthly_tokens=50000,
        )

        # Assert
        assert quota.current_daily_text == 25
        assert quota.current_daily_image == 5
        assert quota.current_monthly_tokens == 50000

    def test_user_quota_needs_daily_reset_expired(self):
        """测试: 判断每日配额是否需要重置 - 已过期"""
        # Arrange
        quota = UserQuota(
            user_id=uuid.uuid4(),
            daily_text_requests=100,
            daily_reset_at=datetime.now(UTC) - timedelta(days=1),
        )

        # Act & Assert
        assert quota.needs_daily_reset() is True

    def test_user_quota_needs_daily_reset_not_expired(self):
        """测试: 判断每日配额是否需要重置 - 未过期"""
        # Arrange
        quota = UserQuota(
            user_id=uuid.uuid4(),
            daily_text_requests=100,
            daily_reset_at=datetime.now(UTC) + timedelta(hours=12),
        )

        # Act & Assert
        assert quota.needs_daily_reset() is False

    def test_user_quota_needs_monthly_reset_expired(self):
        """测试: 判断每月配额是否需要重置 - 已过期"""
        # Arrange
        quota = UserQuota(
            user_id=uuid.uuid4(),
            monthly_token_limit=1000000,
            monthly_reset_at=datetime.now(UTC) - timedelta(days=1),
        )

        # Act & Assert
        assert quota.needs_monthly_reset() is True

    def test_user_quota_needs_monthly_reset_not_expired(self):
        """测试: 判断每月配额是否需要重置 - 未过期"""
        # Arrange
        quota = UserQuota(
            user_id=uuid.uuid4(),
            monthly_token_limit=1000000,
            monthly_reset_at=datetime.now(UTC) + timedelta(days=15),
        )

        # Act & Assert
        assert quota.needs_monthly_reset() is False

    def test_user_quota_repr(self):
        """测试: 模型字符串表示"""
        # Arrange
        user_id = uuid.uuid4()
        quota = UserQuota(
            user_id=user_id,
            daily_text_requests=100,
        )

        # Act
        repr_str = repr(quota)

        # Assert
        assert "UserQuota" in repr_str


@pytest.mark.unit
class TestQuotaUsageLog:
    """QuotaUsageLog 模型测试"""

    def test_create_quota_usage_log_text(self):
        """测试: 创建文本能力用量日志"""
        # Arrange
        user_id = uuid.uuid4()

        # Act
        log = QuotaUsageLog(
            user_id=user_id,
            capability="text",
            provider="dashscope",
            model="qwen-turbo",
            key_source="system",
            input_tokens=100,
            output_tokens=200,
        )

        # Assert
        assert log.user_id == user_id
        assert log.capability == "text"
        assert log.provider == "dashscope"
        assert log.model == "qwen-turbo"
        assert log.key_source == "system"
        assert log.input_tokens == 100
        assert log.output_tokens == 200

    def test_create_quota_usage_log_image(self):
        """测试: 创建图像能力用量日志"""
        # Arrange
        user_id = uuid.uuid4()

        # Act
        log = QuotaUsageLog(
            user_id=user_id,
            capability="image",
            provider="dashscope",
            model="wanx-v1",
            key_source="user",
            image_count=4,
            cost_estimate=0.08,
        )

        # Assert
        assert log.capability == "image"
        assert log.key_source == "user"
        assert log.image_count == 4
        assert log.cost_estimate == 0.08

    def test_quota_usage_log_repr(self):
        """测试: 模型字符串表示"""
        # Arrange
        log = QuotaUsageLog(
            user_id=uuid.uuid4(),
            capability="text",
            provider="openai",
            model="gpt-4",
            key_source="system",
        )

        # Act
        repr_str = repr(log)

        # Assert
        assert "QuotaUsageLog" in repr_str
