"""quota 子包 — 上下游套餐配额算子、guard、配置缓存与 callback 结算。

迁移自 application/ 根目录平铺文件，详见
docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md M3。

子分组：
- quota_plan_*：通用滚动窗口配额算子（Redis）+ 用量落库 + callback 共享
- provider_quota_*：上游扁平配额 pre-call 校验 + 配置缓存 + callback 结算
- entitlement_*：下游客户套餐 guard + 配置缓存 + 模型态 + callback 结算
- usage_bucket_flusher：窗口桶用量合并刷写（budget/quota 共享表）
"""
