# 亚马逊视频生成集成文档

本文档描述了亚马逊产品视频生成功能的架构和使用方式。

> **完整实现说明**：项目根目录 `docs/VIDEO_GENERATION_IMPLEMENTATION.md` 提供从数据模型、后端用例、厂商客户端、REST API、前端页面到 Agent 工具的完整实现说明，便于维护与扩展。

## 概述

亚马逊视频生成功能允许用户通过 Agent 对话或直接通过任务列表页面创建和管理视频生成任务。系统会调用 GIIKIN API 生成产品展示视频。

## 架构

### 后端

```
backend/
├── domains/agent/
│   ├── application/
│   │   └── video_task_use_case.py      # 视频任务用例
│   ├── infrastructure/
│   │   ├── models/
│   │   │   └── video_gen_task.py       # 视频任务模型
│   │   ├── repositories/
│   │   │   └── video_gen_task_repository.py  # 视频任务仓储
│   │   ├── video_api/
│   │   │   ├── __init__.py
│   │   │   └── client.py               # GIIKIN API 客户端
│   │   └── tools/
│   │       └── amazon_video_tools.py   # Agent 工具
│   └── presentation/
│       └── video_task_router.py        # API 路由
└── alembic/versions/
    └── 20260202_add_video_gen_tasks.py # 数据库迁移
```

### 前端

```
frontend/src/
├── api/
│   └── videoTask.ts                    # API 客户端
├── types/
│   └── video-task.ts                   # 类型定义
└── pages/video-tasks/
    ├── index.tsx                       # 任务创建与进度页面
    ├── history.tsx                    # 历史任务列表
    └── components/
        ├── create-form.tsx             # 创建任务表单（主入口）
        └── detail-dialog.tsx           # 任务详情对话框
```

## 配置

### 环境变量

在 `.env` 文件中配置 GIIKIN API 凭证：

```bash
# GIIKIN 视频生成 API
GIIKIN_CLIENT_ID=your-client-id
GIIKIN_CLIENT_SECRET=your-client-secret
GIIKIN_BASE_URL=https://openapi.giikin.com  # 可选，默认值
```

## API 端点

### 任务管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/video-tasks` | 获取任务列表 |
| GET | `/api/v1/video-tasks/{id}` | 获取任务详情 |
| POST | `/api/v1/video-tasks` | 创建任务 |
| PATCH | `/api/v1/video-tasks/{id}` | 更新任务 |
| POST | `/api/v1/video-tasks/{id}/submit` | 提交任务 |
| POST | `/api/v1/video-tasks/{id}/poll` | 轮询状态 |
| POST | `/api/v1/video-tasks/{id}/cancel` | 取消任务 |
| DELETE | `/api/v1/video-tasks/{id}` | 删除任务 |

### 请求示例

**创建任务：**

```json
POST /api/v1/video-tasks
{
  "prompt_text": "生成一个产品展示视频...",
  "prompt_source": "user_provided",
  "reference_images": ["https://example.com/image1.jpg"],
  "marketplace": "jp",
  "auto_submit": true
}
```

**响应：**

```json
{
  "id": "uuid",
  "status": "running",
  "workflow_id": "xxx",
  "run_id": "xxx",
  "prompt_text": "...",
  "marketplace": "jp",
  "created_at": "2026-02-02T10:00:00Z"
}
```

## Agent 工具

以下工具可在 Agent 对话中使用：

### amazon_video_submit

提交视频生成任务。

**参数：**
- `prompt` (必填): 完整的视频生成提示词
- `reference_images`: 参考图片 URL 列表
- `marketplace`: 目标站点 (默认 "jp")
- `session_id`: 关联会话 ID

### amazon_video_poll

查询任务状态。

**参数：**
- `task_id` (必填): 任务 ID
- `once`: 是否单次查询 (默认 true)

### amazon_product_research

产品调研工具。

**参数：**
- `product_link`: 产品链接
- `extra_description`: 产品描述
- `reference_images`: 参考图片

### amazon_competitor_research

竞品调研工具。

**参数：**
- `competitor_link`: 竞品链接
- `competitor_description`: 竞品描述

## MCP 动态工具

可通过 MCP 管理 API 添加视频相关的动态工具：

**支持的 tool_type：**
- `amazon_video_submit`: 视频提交
- `amazon_video_poll`: 视频轮询

## 任务状态

| 状态 | 描述 |
|------|------|
| pending | 待提交 |
| running | 已提交，等待生成 |
| completed | 生成完成 |
| failed | 生成失败 |
| cancelled | 已取消 |

## 厂商 API 状态码

| 状态码 | 含义 |
|--------|------|
| 0 | 未知 |
| 1 | 运行中 |
| 2 | 已完成 |
| 3 | 失败 |
| 4 | 已取消 |
| 5 | 已终止 |
| 6 | 已重新创建 |
| 7 | 超时 |

## 使用流程

### 通过 Agent 对话

1. 用户在对话中提供产品关键词和描述
2. Agent 使用 `amazon_product_research` 调研产品
3. Agent 生成分镜设计并展示给用户
4. 用户确认后，Agent 使用 `amazon_video_submit` 提交任务
5. Agent 使用 `amazon_video_poll` 轮询状态
6. 完成后 Agent 返回视频链接

### 通过任务列表页面

1. 访问 `/video-tasks` 页面
2. 点击「创建任务」
3. 填写提示词和参数
4. 提交任务
5. 在列表中查看状态和结果

## 数据库迁移

执行迁移创建 `video_gen_tasks` 表：

```bash
cd backend
alembic upgrade head
```

## 注意事项

1. **Token 管理**: VideoAPIClient 会自动缓存和刷新 OAuth2 token
2. **轮询策略**: 首次轮询前等待 4 分钟，之后每 30 秒轮询一次
3. **超时处理**: 默认最大等待时间 15 分钟
4. **错误处理**: 失败的任务会记录错误信息到 `error_message` 字段
