# 术语使用规范

## 概述

本文档定义了 AI Agent 系统中术语的使用规范，确保用户界面、代码实现和文档的一致性。

## 核心原则

1. **用户可见层**：使用自然语言，优先选择"对话"
2. **技术实现层**：使用标准技术术语 `Session`
3. **文档注释**：明确说明术语对应关系

## 术语对照表

| 场景 | 使用术语 | 示例 | 说明 |
|------|---------|------|------|
| **用户界面（UI）** | 对话 | "对话历史"、"开始新对话"、"对话记录" | 用户友好，自然语言 |
| **前端代码注释** | 对话 | `// 加载对话历史消息` | 与 UI 保持一致 |
| **后端 API 路径** | `session` | `/api/v1/sessions` | 标准 RESTful 命名 |
| **数据库表名** | `sessions` | `CREATE TABLE sessions` | 技术标准术语 |
| **代码变量/类名** | `Session` | `SessionService`, `session_id` | 技术实现标准 |
| **错误消息（用户可见）** | 对话 | "对话未找到" | 用户友好 |
| **错误消息（日志）** | `Session` | `Session not found: {id}` | 技术调试用 |

## 业界最佳实践参考

### 主流产品术语使用

| 产品 | 用户界面 | 技术实现 | 说明 |
|------|---------|---------|------|
| **OpenAI ChatGPT** | Conversation | Thread/Conversation | UI 使用 "Conversation" |
| **Anthropic Claude** | Conversation | Thread | UI 使用 "Conversation" |
| **Microsoft Agent Framework** | Conversation | Thread/ChatThread | 技术层用 Thread |
| **Kimi AI** | 对话 | Session/Thread | 中文 UI 用"对话" |
| **通义千问** | 对话 | Session | 中文 UI 用"对话" |

### 业界共识

1. **用户界面层**：优先使用自然语言术语
   - 英文产品：`Conversation` / `Chat`
   - 中文产品：`对话` / `聊天`

2. **技术实现层**：使用标准技术术语
   - `Session`：表示一次连接/生命周期
   - `Thread`：表示对话线程（部分产品使用）
   - `Conversation`：表示对话内容（部分产品使用）

3. **API 设计**：保持 RESTful 标准
   - 资源路径：`/sessions` 或 `/conversations`
   - 资源标识：`session_id` 或 `conversation_id`

## 本系统实现

### 当前状态

✅ **已统一**：
- 前端 UI：统一使用"对话"
- 前端注释：统一使用"对话"
- 后端代码：使用 `Session`（技术实现）
- 后端注释：使用"对话"（用户视角）

### 术语映射

```
用户视角          →  技术实现
─────────────────────────────────
对话              →  Session
对话历史          →  sessions table
对话 ID           →  session_id
开始新对话        →  create session
对话记录          →  session records
```

### 错误处理示例

**用户可见错误**：
```typescript
// 前端显示
"对话未找到，请刷新页面或检查网络连接"
```

**日志记录**：
```python
# 后端日志
logger.error("Session not found: %s", session_id)
```

## 实施指南

### 开发时注意事项

1. **编写 UI 文案时**：
   - ✅ 使用"对话"、"对话历史"、"新对话"
   - ❌ 避免使用"会话"、"Session"

2. **编写代码注释时**：
   - ✅ 用户相关功能：使用"对话"
   - ✅ 技术实现说明：可以使用 `Session` 并说明对应关系

3. **API 设计时**：
   - ✅ 保持 RESTful 标准：`/api/v1/sessions`
   - ✅ 响应字段可以使用 `session_id`（技术标识）

4. **错误处理时**：
   - ✅ 用户可见：转换为"对话"相关术语
   - ✅ 日志记录：保持技术术语便于调试

## 常见问题

### Q: 为什么不在代码中也统一为"对话"？

**A**: 技术实现层使用 `Session` 是业界标准做法，原因：
1. 与现有框架和库保持一致（如 SQLAlchemy、FastAPI）
2. 便于开发者理解和维护
3. 避免大规模重构带来的风险
4. 符合 RESTful API 设计规范

### Q: 文档中应该使用哪个术语？

**A**: 根据文档类型：
- **用户文档**：使用"对话"
- **技术文档**：可以使用 `Session`，但需说明对应关系
- **API 文档**：使用 `Session`（技术术语）

### Q: 错误消息应该怎么处理？

**A**:
- **用户可见**：转换为友好的"对话"相关消息
- **日志/调试**：保持技术术语 `Session`

## 更新记录

- 2024-XX-XX: 初始版本，统一术语规范
