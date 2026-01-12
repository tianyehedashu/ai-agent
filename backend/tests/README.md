# 测试文档

本目录包含 AI Agent 系统的所有测试代码。

## 测试结构

```
tests/
├── unit/              # 单元测试 (~70%)
│   ├── core/         # 核心模块测试
│   ├── services/     # 服务层测试
│   └── utils/        # 工具函数测试
├── integration/      # 集成测试 (~20%)
│   └── api/          # API 端点测试
├── e2e/              # 端到端测试 (~10%)
├── fixtures/          # 测试数据工厂
└── mocks/            # Mock 对象
```

## 运行测试

### 运行所有测试
```bash
cd backend
pytest
```

### 运行单元测试
```bash
pytest tests/unit -v
```

### 运行集成测试
```bash
pytest tests/integration -v
```

### 运行特定测试文件
```bash
pytest tests/unit/utils/test_token.py -v
```

### 运行并查看覆盖率
```bash
pytest --cov=backend --cov-report=html
```

## 测试标记

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.e2e` - 端到端测试
- `@pytest.mark.slow` - 慢速测试
- `@pytest.mark.llm` - 需要 LLM API 的测试

## 测试覆盖率目标

- 核心业务逻辑: ≥ 90%
- 工具系统: ≥ 85%
- API 层: ≥ 80%
- 总体目标: ≥ 80%

## 编写测试指南

1. **使用 AAA 模式**: Arrange (准备) → Act (执行) → Assert (断言)
2. **测试命名**: `test_<功能>_<条件>_<预期结果>`
3. **测试隔离**: 每个测试应该独立，不依赖其他测试
4. **使用 Fixtures**: 复用测试数据和配置
5. **Mock 外部依赖**: LLM API、数据库等

## 示例

```python
import pytest
from unittest.mock import AsyncMock

class TestExample:
    @pytest.fixture
    def mock_service(self):
        """Mock 服务"""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_example_function(self, mock_service):
        """测试示例函数"""
        # Arrange
        mock_service.fetch.return_value = {"key": "value"}
        
        # Act
        result = await example_function(mock_service)
        
        # Assert
        assert result == expected_value
```
