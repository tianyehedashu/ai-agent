"""用户模型（BYOK）接入通道标识。

与 LiteLLM 路由 ``provider`` 段及设置页选项一致；供 Presentation / Application 共用，
避免在 ``user_model_use_case`` 模块上产生 presentation 依赖。

与 Gateway ``USER_GATEWAY_CREDENTIAL_PROVIDERS``（``domains.gateway.domain.types``）的
关系：后者约束 **用户级 Gateway 凭据** 可写 API 的枚举，**不含** ``custom``；
用户模型允许 ``custom``，表示自定义 Base URL + 模型 ID 组合。
"""

USER_MODEL_VALID_PROVIDERS: frozenset[str] = frozenset(
    {
        "openai",
        "deepseek",
        "dashscope",
        "anthropic",
        "zhipuai",
        "volcengine",
        "custom",
    }
)

__all__ = ["USER_MODEL_VALID_PROVIDERS"]
