"""access 子包 — Gateway 鉴权与团队上下文用例及装配工厂。

迁移自 application/ 根目录平铺文件（M5），详见
docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md。

子分组：
- 用例：gateway_access_use_case（Bearer vkey、平台 sk-* 代理鉴权、团队解析、vkey touch）
- 装配：gateway_access_factory（组合根工厂，注入 identity ApiKey 端口）
"""

from .gateway_access_factory import build_gateway_access_use_case
from .gateway_access_use_case import GatewayAccessUseCase

__all__ = ["GatewayAccessUseCase", "build_gateway_access_use_case"]
