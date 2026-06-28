"""catalog 子包 — Gateway 模型目录种子/同步/列表/选择器/能力推断。

迁移自 application/ 根目录平铺文件（M4），详见
docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md。

子分组：
- 种子/同步：gateway_catalog_seed / config_catalog_sync / gateway_catalog_maintenance
- 列表读侧：gateway_model_listing / model_list_pipeline / model_list_*_credentials
- 选择器读侧：model_selector_reads / model_selector_list_reads / chat_model_selector_reads
- 能力推断：catalog_capability / upstream_catalog_capability_prep / upstream_model_types_for_catalog
- 解析/投影：model_or_route_resolution / granted_route_listing / granted_route_selector_items
- 辅助：personal_models / scenario_defaults / model_reference_prune / user_models_migration
- 现有保留：gateway_model_tags_pipeline / litellm_capability_hint
"""

# 兼容 re-export（历史调用方 from domains.gateway.application.catalog import ...）
from domains.gateway.application.upstream.litellm_capability_hint import (
    merge_litellm_capability_hints,
    merge_litellm_reasoning_hint,
)

from .gateway_model_tags_pipeline import build_gateway_model_tags

__all__ = [
    "build_gateway_model_tags",
    "merge_litellm_capability_hints",
    "merge_litellm_reasoning_hint",
]
