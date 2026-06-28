"""bridge 子包 — Gateway 跨域内部桥接（agent 域 ↔ gateway 域）。

迁移自 application/ 根目录平铺文件（M11），详见
docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md。

子分组：
- 桥接核心：internal_bridge（GatewayBridge 实现）、internal_bridge_actor（演员上下文）
- 归因：bridge_attribution（请求归因到 gateway 上下文）
- 目录/前缀：bridge_catalog、litellm_real_model_prefix、litellm_bridge_payload
- 工厂/日志：gateway_proxy_factory（agent 侧代理工厂）、gateway_internal_log_context
- 端口注册：listing_studio_image_port_registry（bootstrap 装配点）
- 计费上下文：billing_context（agent 域共享的计费上下文对象）
"""
