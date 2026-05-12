"""
Gateway Domain - AI 网关领域

基于 LiteLLM Python SDK 的 AI Gateway 实现，提供：
- OpenAI 兼容入口（/v1/chat/completions, /v1/embeddings, ...）
- 团队-虚拟 Key 体系
- 模型路由与三类 Fallback
- 预算/限流/调用日志/告警
- 团队凭据池

充分复用 LiteLLM 的 Router、CustomLogger、CustomGuardrail、completion_cost
等能力，并与现有 identity/RBAC 紧密集成。
"""
