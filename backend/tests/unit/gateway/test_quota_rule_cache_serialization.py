"""``quota_rule_cache`` 序列化 / 反序列化往返单测。

回归防护：``_quota_rule_to_dict`` 与 ``_dict_to_quota_rule`` 必须对称保留所有字段，
特别是 ``limit_images`` / ``current_images``（图片配额维度新增字段）。
缓存命中后字段丢失会导致前端展示缺图、配额计算偏差。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from domains.gateway.application.management.quota_rule_cache import (
    _dict_to_quota_rule,
    _quota_rule_to_dict,
)
from domains.gateway.application.management.quota_rule_read_model import (
    QuotaRuleKey,
    QuotaRuleLimits,
    QuotaRuleReadModel,
    QuotaRuleSourceRef,
    QuotaRuleUsage,
)


def _make_rule(
    *,
    limit_images: int | None = None,
    current_images: int | None = None,
) -> QuotaRuleReadModel:
    """构造覆盖全字段的 QuotaRuleReadModel 测试夹具。"""
    return QuotaRuleReadModel(
        key=QuotaRuleKey(
            team_id=uuid.uuid4(),
            layer="platform",
            user_id=uuid.uuid4(),
            credential_id=None,
            model_name="dall-e-3",
            period="daily",
            window_seconds=None,
            reset_strategy="calendar_daily_utc",
            access_kind="none",
            access_id=None,
            quota_label="default",
            target_kind="tenant",
            target_id=uuid.uuid4(),
            period_timezone="UTC",
            period_reset_minutes=0,
            period_reset_day=1,
        ),
        source_ref=QuotaRuleSourceRef(
            layer="platform",
            budget_id=uuid.uuid4(),
            plan_id=None,
            quota_id=None,
        ),
        limits=QuotaRuleLimits(
            limit_usd=Decimal("100.00"),
            soft_limit_usd=Decimal("80.00"),
            limit_tokens=None,
            limit_requests=None,
            limit_images=limit_images,
            unit_price_usd_per_token=Decimal("0.000002"),
            unit_price_usd_per_request=Decimal("0.01"),
        ),
        usage=QuotaRuleUsage(
            current_usd=Decimal("12.34"),
            current_tokens=None,
            current_requests=None,
            current_images=current_images,
            window_start=datetime(2026, 6, 26, 0, 0, tzinfo=UTC),
            reset_at=datetime(2026, 6, 27, 0, 0, tzinfo=UTC),
            budget_reset_at=datetime(2026, 6, 27, 0, 0, tzinfo=UTC),
        ),
        plan_label="测试套餐",
        is_active=True,
    )


class TestQuotaRuleCacheSerialization:
    def test_round_trip_preserves_limit_images_and_current_images(self) -> None:
        """新增的 images 维度字段必须往返保留。"""
        rule = _make_rule(limit_images=50, current_images=12)
        restored = _dict_to_quota_rule(_quota_rule_to_dict(rule))
        assert restored.limits.limit_images == 50
        assert restored.usage is not None
        assert restored.usage.current_images == 12

    def test_round_trip_preserves_none_images(self) -> None:
        """``limit_images=None`` / ``current_images=None`` 也须往返保留。"""
        rule = _make_rule(limit_images=None, current_images=None)
        restored = _dict_to_quota_rule(_quota_rule_to_dict(rule))
        assert restored.limits.limit_images is None
        assert restored.usage is not None
        assert restored.usage.current_images is None

    def test_round_trip_preserves_decimal_fields(self) -> None:
        """``Decimal`` 字段经 ``str`` 序列化后应还原为 ``Decimal`` 类型。"""
        rule = _make_rule(limit_images=10, current_images=3)
        restored = _dict_to_quota_rule(_quota_rule_to_dict(rule))
        assert isinstance(restored.limits.limit_usd, Decimal)
        assert restored.limits.limit_usd == Decimal("100.00")
        assert restored.limits.soft_limit_usd == Decimal("80.00")
        assert restored.limits.unit_price_usd_per_token == Decimal("0.000002")
        assert restored.limits.unit_price_usd_per_request == Decimal("0.01")
        assert restored.usage is not None
        assert isinstance(restored.usage.current_usd, Decimal)
        assert restored.usage.current_usd == Decimal("12.34")

    def test_round_trip_preserves_uuid_fields(self) -> None:
        """``UUID`` 字段经 ``str`` 序列化后应还原为 ``UUID`` 类型。"""
        rule = _make_rule(limit_images=10, current_images=0)
        restored = _dict_to_quota_rule(_quota_rule_to_dict(rule))
        from uuid import UUID

        assert isinstance(restored.key.team_id, UUID)
        assert restored.key.team_id == rule.key.team_id
        assert isinstance(restored.key.user_id, UUID)
        assert restored.key.user_id == rule.key.user_id
        assert isinstance(restored.source_ref.budget_id, UUID)
        assert restored.source_ref.budget_id == rule.source_ref.budget_id

    def test_round_trip_preserves_datetime_fields(self) -> None:
        """``datetime`` 字段经 ISO 字符串序列化后应还原为 ``datetime``。"""
        rule = _make_rule(limit_images=10, current_images=0)
        restored = _dict_to_quota_rule(_quota_rule_to_dict(rule))
        assert restored.usage is not None
        assert isinstance(restored.usage.window_start, datetime)
        assert restored.usage.window_start == rule.usage.window_start
        assert isinstance(restored.usage.reset_at, datetime)
        assert restored.usage.reset_at == rule.usage.reset_at
        assert restored.usage.budget_reset_at == rule.usage.budget_reset_at

    def test_round_trip_preserves_other_dimensions(self) -> None:
        """既有维度（usd/tokens/requests）不应受 images 维度新增影响。"""
        rule = _make_rule(limit_images=10, current_images=3)
        restored = _dict_to_quota_rule(_quota_rule_to_dict(rule))
        assert restored.limits.limit_usd == Decimal("100.00")
        assert restored.limits.limit_tokens is None
        assert restored.limits.limit_requests is None
        assert restored.usage is not None
        assert restored.usage.current_usd == Decimal("12.34")
        assert restored.usage.current_tokens is None
        assert restored.usage.current_requests is None

    def test_round_trip_preserves_usage_none(self) -> None:
        """``usage=None`` 分支也应往返保留。"""
        rule = QuotaRuleReadModel(
            key=QuotaRuleKey(
                team_id=uuid.uuid4(),
                layer="platform",
                user_id=None,
                credential_id=None,
                model_name=None,
                period="daily",
                window_seconds=None,
                reset_strategy="calendar_daily_utc",
                access_kind="none",
                access_id=None,
                quota_label="default",
                target_kind="tenant",
                target_id=None,
            ),
            source_ref=QuotaRuleSourceRef(layer="platform"),
            limits=QuotaRuleLimits(
                limit_usd=None,
                soft_limit_usd=None,
                limit_tokens=None,
                limit_requests=None,
                limit_images=None,
            ),
            usage=None,
            plan_label=None,
            is_active=True,
        )
        restored = _dict_to_quota_rule(_quota_rule_to_dict(rule))
        assert restored.usage is None
        assert restored.limits.limit_images is None

    def test_serialized_dict_contains_images_keys(self) -> None:
        """序列化字典必须显式包含 ``limit_images`` / ``current_images`` 键。"""
        rule = _make_rule(limit_images=50, current_images=12)
        data = _quota_rule_to_dict(rule)
        assert "limit_images" in data["limits"]
        assert data["limits"]["limit_images"] == 50
        assert data["usage"] is not None
        assert "current_images" in data["usage"]
        assert data["usage"]["current_images"] == 12
