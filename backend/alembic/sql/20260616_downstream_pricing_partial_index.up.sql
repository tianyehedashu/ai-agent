-- 部分索引：只覆盖当前生效的行（effective_to 为 NULL）
-- 本表采用 soft-close，close_effective 将 effective_to 设为当前时间后不会再变更，
-- 因此 IS NULL 即代表活跃行。使用 IMMUTABLE 条件符合 PostgreSQL 对部分索引谓词的要求。
CREATE INDEX ix_downstream_model_pricing_lookup_active
ON downstream_model_pricing (scope, scope_id, gateway_model_id, effective_from)
WHERE effective_to IS NULL;

-- 修复统计信息，确保优化器选择正确索引
ANALYZE downstream_model_pricing;
