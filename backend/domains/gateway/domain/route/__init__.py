"""route 子包 — Gateway domain route 业务能力聚合。

迁移自 domain/ 根级与 policies/（D 系列里程碑），详见
docs/gateway/DOMAIN_SUBPACKAGE_MIGRATION.md。
"""

from domains.gateway.domain.route.route_capability import route_capability_snapshot

__all__ = ["route_capability_snapshot"]
