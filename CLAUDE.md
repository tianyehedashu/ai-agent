# AI Agent 项目规范

## 类型安全

| 语言 | 复用 | 禁止 |
|------|------|------|
| Python | `core.types.*`, `core.utils.message_formatter.*` | `Any`, `dict` 无类型, `# type: ignore` |
| TypeScript | `@/types` | `any`, `as any`, `@ts-ignore` |

## 原则

- **DRY** - 复用现有类型和工具函数
- **分层** - API / Service / Model 职责分离

## 详细规范

[backend/docs/CODE_STANDARDS.md](backend/docs/CODE_STANDARDS.md) | [frontend/docs/CODE_STANDARDS.md](frontend/docs/CODE_STANDARDS.md)
