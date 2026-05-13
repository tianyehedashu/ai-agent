对当前改动做 **规范 + 架构 + 重复/遗留** 审核，并给出可执行建议。

## 必读

- `backend/docs/CODE_STANDARDS.md`（目录、`libs` vs `domains`、**应用端口**在 `application/` 不在 `libs`）
- 仓库根 `AGENTS.md`（导入路径与分层）
- 架构补充：`backend/docs/ARCHITECTURE.md`、`backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md`（Gateway 边界）

## 检查维度

1. **架构**：Presentation → Application → Domain ← Infrastructure；跨域 **Protocol/DTO** 由 **提供方域** `application/` 声明（如 `SessionApplicationPort`、`GatewayProxyProtocol`），不在 `libs/` 堆业务契约。
2. **遗留**：禁止再引入已移除路径（如历史 `libs/gateway`）；兼容分支是否可删、是否重复实现。
3. **类型与风格**：与 `pyproject.toml` 中 Ruff / Pyright 约定一致；禁止无必要的 `Any`、`# type: ignore`。
4. **测试**：改动涉及行为时，补充或更新 `tests/unit/` 或 `tests/integration/` 相关用例。

## 建议本地命令（`backend/` 下）

```powershell
uv run ruff check .
uv run pyright <涉及的路径或包>
uv run pytest tests/unit/<相关目录> -q --tb=short
# 有 HTTP/DB 行为时：
uv run pytest tests/integration/ -q --tb=short
```

输出：按 **问题 → 依据（文档/原则）→ 建议修改** 列出；无问题时简要说明已核对项。
