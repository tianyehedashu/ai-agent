"""配额规则列表分页 response 组装。"""

from __future__ import annotations

from domains.gateway.application.management.quota_rule_read_model import QuotaRuleReadModel
from domains.gateway.presentation.quota_rule_response import quota_rule_to_response
from domains.gateway.presentation.schemas.common import QuotaRuleListResponse
from libs.api.pagination import build_page


def build_quota_rule_list_response(
    *,
    rows: list[QuotaRuleReadModel],
    total: int,
    page: int,
    page_size: int,
) -> QuotaRuleListResponse:
    items = [quota_rule_to_response(row) for row in rows]
    envelope = build_page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return QuotaRuleListResponse(**envelope.model_dump())


__all__ = ["build_quota_rule_list_response"]
