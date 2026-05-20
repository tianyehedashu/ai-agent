# Changelog

## Unreleased

### Added

- **Listing Studio**（原 product-info）：主 API 路径 `/api/v1/listing-studio`，前端路由 `/listing-studio`，侧栏「Listing 创作」。
- Gateway 模型对齐：`model_selection_policy`、可见 catalog 默认解析；无可见模型时明确错误。
- `GET /listing-studio/capabilities` 返回 `{ capabilities, execution_layers }`（编排真源在后端）。
- `RunPipelineBody.model_overrides` 支持一键执行按步指定模型。

### Deprecated

- API `/api/v1/product-info/*`：响应带 `Deprecation: true` 与 `Link: </api/v1/listing-studio>; rel="successor-version"`。
- 前端 `/product-info/*` 重定向至 `/listing-studio/*`。
- `get_product_info_service` / `get_product_info_prompt_service` deps 别名。

**Alias 移除条件**：2 个 minor 版本或 2026-08-18（90 天）后删除 `/product-info` 路由与上述 deps 别名。
