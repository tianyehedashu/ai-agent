# E2E 测试 (端到端测试)

## 什么是 E2E 测试？

E2E 测试也叫 **API 集成测试** 或 **功能测试**，它们：

- ✅ 真正调用 API（不使用 Mock）
- ✅ 需要完整的运行环境
- ✅ 验证端到端的业务流程
- ❌ 不通过浏览器操作（那是 UI E2E 测试）

## 测试分类

| 类型 | 说明 | 运行命令 | 需要环境 |
|------|------|----------|----------|
| **单元测试** | 测试单个函数/类，大量 Mock | `make test-unit` | ❌ |
| **集成测试** | 使用 TestClient，不启动服务 | `make test-integration` | ❌ |
| **E2E 测试** | 真正调用 API，完整流程 | `make test-e2e` | ✅ |
| **LLM 测试** | 测试 LLM 提供商 | `make test-llm-providers` | ✅ API Key |

## 运行方式

### 1. 启动环境

```bash
# 启动数据库和 Redis
docker-compose up -d

# 启动后端服务
cd backend
make dev
```

### 2. 运行 E2E 测试

```bash
# 在另一个终端
cd backend
make test-e2e
```

### 3. 日常开发测试

```bash
# 不需要启动环境，排除 E2E 测试
make test
```

## 测试文件

```
tests/e2e/
├── __init__.py
├── README.md
├── test_chat_api_e2e.py      # Chat API 端到端测试
└── test_agent_api_e2e.py     # Agent API 端到端测试（待添加）
```

## 编写 E2E 测试

### 标记

所有 E2E 测试必须使用 `@pytest.mark.e2e` 标记：

```python
import pytest

@pytest.mark.e2e
class TestChatAPIE2E:
    """Chat API 端到端测试"""

    @pytest.mark.asyncio
    async def test_chat_single_message(self):
        """测试: 发送单条消息"""
        # 真正调用 API
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            response = await client.post("/api/v1/chat", json={"message": "hello"})
            assert response.status_code == 200
```

### 最佳实践

1. **使用 httpx** - 支持同步和异步 HTTP 调用
2. **适当的超时** - LLM 调用可能需要较长时间
3. **清理测试数据** - 避免影响其他测试
4. **跳过条件** - 环境不满足时使用 `pytest.skip()`

## 与其他测试类型的区别

### 单元测试 vs E2E 测试

```python
# 单元测试 - Mock LLM
@pytest.mark.unit
async def test_chat_service():
    with patch.object(llm_gateway, "chat") as mock_chat:
        mock_chat.return_value = {"content": "Hello"}
        result = await chat_service.chat("Hi")
        assert result == "Hello"

# E2E 测试 - 真正调用
@pytest.mark.e2e
async def test_chat_api():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.post("/api/v1/chat", json={"message": "Hi"})
        assert response.status_code == 200
```

### 集成测试 vs E2E 测试

```python
# 集成测试 - 使用 TestClient，不启动服务
@pytest.mark.integration
def test_chat_endpoint(client: TestClient):
    response = client.post("/api/v1/chat", json={"message": "Hi"})
    assert response.status_code == 200

# E2E 测试 - 真正的网络调用
@pytest.mark.e2e
async def test_chat_endpoint():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.post("/api/v1/chat", json={"message": "Hi"})
        assert response.status_code == 200
```
