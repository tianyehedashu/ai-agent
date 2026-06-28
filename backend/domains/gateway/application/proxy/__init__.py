"""proxy 子包 — Gateway 代理热路径（对外代理上游 LLM）。

迁移自 application/ 根目录平铺文件（M10），详见
docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md。

子分组：
- 门面：proxy_use_case（端到端代理用例编排）
- 上下文/守卫：proxy_context、proxy_guard、proxy_inbound_preflight、proxy_allowed_models
- LiteLLM 适配：proxy_litellm_client、proxy_litellm_kwargs、anthropic_native_adapt、prompt_cache_middleware
- 元数据/头：proxy_metadata_builder、proxy_rate_limit_headers、proxy_router_team_metadata、proxy_timing
- 路由调用：proxy_router_invoke、proxy_model_list_reads、proxy_vision_image_urls
- 流水线：proxy_chat_entries、proxy_chat_pipeline、proxy_non_chat_pipeline、proxy_stream_settlement
- 响应适配：proxy_response_adapter
- 任务登记：proxy_deferred_tasks
- 辅助：preflight_failure_logger、invocation_overrides、platform_api_key_proxy_dto
"""
