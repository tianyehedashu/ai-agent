# RFC: ImageGenPort 与 Gateway 代理面（Listing Studio Phase 3）

> **状态**：评估中，不阻塞 Phase 1/2 上线  
> **范围**：Listing Studio 8 图生图出站统一

## 背景

Phase 1 已将 **模型解析** 对齐 Gateway catalog（`resolve_image_gen_model_for_chat`）。**出站**仍经 `domains/agent/infrastructure/llm/image_generator.py`（httpx 直连 Provider），与 Chat `image_gen` 现状一致，未纳入 Gateway 计量与统一日志。

## 目标

1. Agent 垂直任务只依赖 **`ImageGenPort`**（application 层端口），不直接引用 `ImageGenerator`
2. 可选经 **`GatewayProxyProtocol`** 代理出站，与 Chat 生图共用计费/审计
3. 保持 `ModelCatalogPort` 为模型真源不变

## 提议接口

```python
# domains/agent/application/ports/image_gen_port.py

@dataclass(frozen=True)
class ImageGenRequest:
    prompt: str
    provider: str
    model: str | None
    size: str
    reference_image_url: str | None
    strength: float | None
    api_key: str | None
    api_base: str | None

@dataclass(frozen=True)
class ImageGenResult:
    url: str
    error: str | None = None

class ImageGenPort(Protocol):
    async def generate(self, request: ImageGenRequest) -> ImageGenResult: ...
```

## 实现选项

| 选项 | 说明 | 优缺点 |
|------|------|--------|
| **A. 直连适配器** | `ImageGeneratorImageGenPort` 包装现有 `ImageGenerator` | 改动小；仍不经 Gateway 计量 |
| **B. Gateway 代理** | Gateway 增加/复用 `image_gen` capability 路由，`GatewayImageGenPort` 调内部桥接 | 计量/日志统一；需 Gateway 产品确认 |
| **C. 混合** | 默认 A，团队开启 feature flag 时走 B | 渐进迁移 |

## 迁移步骤（若采纳 B）

1. Gateway：`POST /v1/images/generations` 或内部 RPC 对齐现有 Chat 生图路径
2. `libs/api/deps.py` 注入 `ImageGenPort` 至 `ProductImageGenTaskUseCase`
3. 删除 UseCase 对 `ImageGenerator` 的直接 import
4. 集成测：mock port + 冒烟真实 catalog 解析

## 非目标

- 不在本 RFC 中变更 DB 表 `product_image_gen_*` 命名
- 不阻塞 Listing Studio 重命名与模型解析对齐

## 参考

- `domains/agent/application/product_image_gen_task_use_case.py`
- `domains/gateway/application/ports.py`（`GatewayProxyProtocol`）
- [ARCHITECTURE.md](./ARCHITECTURE.md) Listing Studio BC 节
