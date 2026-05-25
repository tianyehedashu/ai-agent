# 列表 API 分页规范

> **真源**：跨前后端列表分页的唯一规范。`code-check`、新 endpoint 与 UI 列表页均以此为准。  
> 实现代码：**后端** `backend/libs/api/pagination.py` · **前端** `frontend/src/types/index.ts`、`frontend/src/lib/pagination.ts`、`frontend/src/components/pagination-controls.tsx`

---

## 1. 适用范围

| 场景 | 要求 |
|------|------|
| **新增** HTTP 列表 endpoint | **必须** 使用本规范 envelope |
| 已有 `skip` / `limit` / 裸数组列表 | 逐步迁移；新功能不得再增加裸数组 |
| 管理面表格（Gateway 模型、日志等） | 服务端分页 + `PaginationControls` |
| 下拉 / 批量操作需全量 id | 用 `GET .../ids` 或前端 `fetchAllPaginatedPages`；注意 `truncated` |

---

## 2. 契约（JSON snake_case）

### 2.1 查询参数

| 参数 | 类型 | 默认 | 约束 |
|------|------|------|------|
| `page` | int | `1` | ≥ 1，**1-based** |
| `page_size` | int | `20` | 1–200（`MAX_PAGE_SIZE`） |

禁止在新列表 API 使用 `skip` / `limit` / `offset` 作为对外 query（内部 ORM offset 除外）。

### 2.2 响应 envelope

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "has_next": false,
  "has_prev": false
}
```

| 字段 | 含义 |
|------|------|
| `items` | 当前页数据 |
| `total` | 过滤后总条数（非当前页长度） |
| `page` | 当前页码（超出末页时由 `build_page` 钳制） |
| `page_size` | 本页请求大小 |
| `has_next` / `has_prev` | 是否还有下一页 / 上一页 |

**禁止** 列表 endpoint 直接返回 `list[T]` 或 `{ "data": [...] }` 而无上述字段。

### 2.3 扩展字段

列表除 envelope 外可附加元数据（如 `connectivity_summary`），写法：

```python
class GatewayModelListResponse(PaginatedListResponse[GatewayModelResponse]):
    connectivity_summary: ModelConnectivitySummary
```

组装时用 `build_page(...)` 得到 envelope，再 `**envelope.model_dump()` 或专用 builder（见 `gateway_model_list_response.py`）。

### 2.4 批量 id（`/ids`）

不分页返回 id 列表时，响应须含：

```json
{ "ids": ["..."], "truncated": false }
```

当命中服务端 `max_ids`（默认 5000）上限时 `truncated: true`，调用方应缩小筛选或分批。

---

## 3. 后端实现

### 3.1 模块与常量

```python
from libs.api.pagination import (
    DEFAULT_PAGE_SIZE,  # 20
    MAX_PAGE_SIZE,      # 200
    PageParams,
    PaginatedListResponse,
    build_page,
    page_query_params,
    slice_page,
    total_pages,
)
```

### 3.2 分层职责

```
presentation          application                    infrastructure
─────────────         ───────────                    ──────────────
Query → PageParams    ModelListQuery + pipeline      ModelListReadRepository
response_model        编排 filter/sort/page            SQL offset/limit
build_*_response      merge 路径: slice_page 内存分页
```

| 层 | 职责 |
|----|------|
| **presentation** | `page` / `page_size` Query 解析 → `PageParams`；`response_model=PaginatedListResponse[...]` |
| **application** | 业务过滤 / 排序（domain policy）→ 取一页 + `total` |
| **infrastructure** | DB 分页：`repository.paginate_*` + `offset/limit`；**禁止** application 直接 `session.execute` 列表 SQL |
| **domain** | 纯函数：`matches_search`、`sort_registry_rows` 等，不依赖分页 envelope |

### 3.3 两种分页路径

1. **SQL 分页（首选）**：仓储层 `count` + `offset/limit`，application 用 `build_page(items=..., total=..., page=..., page_size=...)`。
2. **内存分页（merge / 可见性合并）**：先 filter + sort 得全量列表，再 `slice_page(rows, page=..., page_size=...)` → `(items, total)` → `build_page`。

### 3.4 Presentation 模板

```python
from typing import Annotated
from fastapi import Depends, Query
from libs.api.pagination import PageParams, page_query_params

# 方式 A：通用依赖
PageDep = Annotated[PageParams, Depends(page_query_params)]

# 方式 B：与业务 filter 合并（见 model_list_query.py）
@router.get("/items", response_model=ItemListResponse)
async def list_items(query: ModelListQueryDep) -> ItemListResponse:
    page = await reads.list_items_page(query)
    return build_item_list_response(page)
```

### 3.5 测试

| 类型 | 要求 |
|------|------|
| 单元 | `tests/unit/libs/api/test_pagination.py` 覆盖 `build_page` / `slice_page` |
| 集成 | 断言响应含 `items, total, page, page_size, has_next, has_prev`；扩展字段一并断言 |
| 命令 | `uv run pytest tests/unit/libs/api/ tests/integration/api/test_*_api.py -q` |

---

## 4. 前端实现

### 4.1 类型（`@/types`）

```typescript
import type { PaginatedList, PageQuery } from '@/types'

interface ItemListResponse extends PaginatedList<Item> {
  connectivity_summary?: Summary  // 可选扩展
}
```

`PageQuery`: `{ page?: number; page_size?: number }`。  
勿在新代码使用 legacy `PaginatedResponse`（camelCase `pageSize` / `hasMore`）。

### 4.2 API adapter

- 列表请求在 `frontend/src/api/<domain>/` 单点封装，`page` / `page_size` 走 query string。
- 扩展 query（`q`, `sort`, `connectivity` 等）与 `PageQuery` 组合为 `*ListQuery` 类型。

### 4.3 UI

- 表格/工作区：**服务端分页**，状态 `page` + `page_size`，翻页重新 fetch。
- 复用 `@/components/pagination-controls`（props 与 envelope 字段对齐）。
- 筛选变更时重置 `page` 为 1；`total === 0` 显示空态，不渲染分页条。

### 4.4 全量拉取（批量操作 / 下拉）

```typescript
import { fetchAllPaginatedPages, MAX_PAGE_SIZE } from '@/lib/pagination'

const all = await fetchAllPaginatedPages((page, page_size) =>
  modelsApi.listModels(teamId, { ...filters, page, page_size })
)
```

- 默认 `page_size = 200`（与后端 `MAX_PAGE_SIZE` 一致）。
- 仅用于**必须跨页**的批量操作；常规定制列表用服务端分页，避免一次拉全表。

---

## 5. code-check 核对清单

审查**新增或改动列表 API** 时逐项勾选：

### 后端

- [ ] Query 使用 `page` + `page_size`（1-based，上限 200），无对外 `skip/limit`
- [ ] `response_model` 继承或使用 `PaginatedListResponse[T]`，非裸 `list[T]`
- [ ] 使用 `build_page` 或等价 builder 填充 `has_next` / `has_prev`，手算字段视为缺陷
- [ ] DB 列表经 repository / ReadRepository 分页，application 不直接写 `session.execute` 列表 SQL
- [ ] 业务 filter/sort 在 domain policy；application 只编排
- [ ] 集成测试断言 envelope 全部字段；有扩展字段则一并断言
- [ ] `/ids` 类 endpoint 返回 `truncated` 当存在上限

### 前端

- [ ] 类型用 `PaginatedList<T>` / `PageQuery`，无 `any`
- [ ] API 经 `src/api/<domain>/` adapter，非页面内散落 fetch
- [ ] 工作区用 `PaginationControls` + 服务端分页 state
- [ ] 批量操作用 `fetchAllPaginatedPages` 或专用 `/ids`；处理 `truncated`
- [ ] 筛选变化重置页码；空结果有 empty state

---

## 6. 参考实现

| 能力 | 路径 |
|------|------|
| 分页原语 | `backend/libs/api/pagination.py` |
| Gateway 列表 query | `backend/domains/gateway/presentation/model_list_query.py` |
| Gateway 列表 pipeline | `backend/domains/gateway/application/model_list_pipeline.py` |
| Gateway 读仓储 | `backend/domains/gateway/infrastructure/repositories/model_list_read_repository.py` |
| Response 组装 | `backend/domains/gateway/presentation/gateway_model_list_response.py` |
| 前端类型 | `frontend/src/types/index.ts` |
| 翻页 helper | `frontend/src/lib/pagination.ts` |
| 分页 UI | `frontend/src/components/pagination-controls.tsx` |
| Gateway 列表示例 | `frontend/src/features/gateway-models/team/team-models-workspace.tsx` |

---

## 7. 迁移说明

旧 endpoint 若仍返回数组，在 PR 中注明迁移计划或 issue；**同一资源的新 endpoint 不得复制旧形态**。  
Session 等历史 `skip/limit` 在各自域内迁移时仍须最终对齐本 envelope。
