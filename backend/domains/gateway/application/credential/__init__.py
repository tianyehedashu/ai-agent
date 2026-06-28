"""credential 子包 — Gateway 凭据环境审计与模型级联。

迁移自 application/ 根目录平铺文件（M9），详见
docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md。

子分组：
- 环境审计：credential_env_audit（启动时对比 env bootstrap 与 DB config-managed api_base）
- 模型级联：credential_model_cascade（凭据启用/停用时同步关联 GatewayModel/SystemGatewayModel.enabled）
"""

from .credential_env_audit import log_config_managed_api_base_drift
from .credential_model_cascade import sync_gateway_models_for_credential_is_active

__all__ = [
    "log_config_managed_api_base_drift",
    "sync_gateway_models_for_credential_is_active",
]
