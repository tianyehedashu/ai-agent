# 测试文档

本文档说明如何运行项目中的测试，包括智谱AI/GLM相关的测试。

## 测试框架

项目使用 **pytest** 作为测试框架，已集成在 `pyproject.toml` 中。

### 依赖安装

确保已安装开发依赖：

```bash
# 使用 uv (推荐)
uv sync --all-extras

# 或使用 pip
pip install -e ".[dev]"
```

## 运行测试

### 使用 Makefile (推荐)

```bash
# 运行所有测试
make test

# 运行单元测试
make test-unit

# 运行集成测试
make test-integration

# 运行测试并生成覆盖率报告
make test-cov

# 监视模式运行测试（文件变化时自动运行）
make test-watch
```

### 直接使用 pytest

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/unit/core/test_llm_providers.py

# 运行特定测试类
pytest tests/unit/core/test_llm_providers.py::TestZhipuAIProvider

# 运行特定测试方法
pytest tests/unit/core/test_llm_providers.py::TestZhipuAIProvider::test_zhipuai_provider_models

# 运行带标记的测试
pytest -m unit          # 只运行单元测试
pytest -m integration   # 只运行集成测试

# 显示详细输出
pytest -v

# 显示打印输出
pytest -s

# 运行测试并生成覆盖率报告
pytest --cov --cov-report=html --cov-report=term-missing
```

### 使用 uv 运行

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/unit/core/test_llm_providers.py
```

## 测试结构

```
tests/
├── conftest.py              # pytest 配置和 fixtures
├── unit/                    # 单元测试
│   ├── core/
│   │   ├── test_llm_gateway.py      # LLM Gateway 测试
│   │   └── test_llm_providers.py    # LLM Providers 测试（包含GLM）
│   ├── services/
│   └── utils/
├── integration/             # 集成测试
│   └── api/
│       ├── test_agent_api.py
│       └── test_system_api.py       # System API 测试（包含GLM模型列表）
└── evaluation/              # 评估测试
```

## 智谱AI/GLM 相关测试

### 单元测试

#### 1. Provider 测试 (`test_llm_providers.py`)

测试智谱AI提供商的模型列表和工具格式化：

```bash
# 运行所有 provider 测试
pytest tests/unit/core/test_llm_providers.py

# 运行智谱AI相关测试
pytest tests/unit/core/test_llm_providers.py::TestZhipuAIProvider
pytest tests/unit/core/test_llm_providers.py::TestGetProvider::test_get_provider_glm
pytest tests/unit/core/test_llm_providers.py::TestGetAllModels::test_get_all_models_zhipuai
```

测试内容：
- ✅ 智谱AI提供商模型列表（glm-4.7, glm-4等）
- ✅ 工具格式化功能
- ✅ 模型名称识别（大小写不敏感）
- ✅ 所有模型列表包含智谱AI

#### 2. Gateway 测试 (`test_llm_gateway.py`)

测试 LLM Gateway 对 GLM 模型的支持：

```bash
# 运行 GLM 相关测试
pytest tests/unit/core/test_llm_gateway.py::TestLLMGateway::test_get_api_key_glm
pytest tests/unit/core/test_llm_gateway.py::TestLLMGateway::test_get_api_key_glm_case_insensitive
pytest tests/unit/core/test_llm_gateway.py::TestLLMGateway::test_get_api_key_glm_no_key
```

测试内容：
- ✅ GLM 模型的 API Key 配置获取
- ✅ 模型名称大小写不敏感
- ✅ 未配置 API Key 时的处理

### 集成测试

#### System API 测试 (`test_system_api.py`)

测试系统API中的模型列表端点：

```bash
# 运行 System API 测试
pytest tests/integration/api/test_system_api.py

# 运行 GLM 相关测试
pytest tests/integration/api/test_system_api.py::TestSystemAPI::test_list_models_simple_includes_glm_when_configured
pytest tests/integration/api/test_system_api.py::TestSystemAPI::test_list_models_simple_excludes_glm_when_not_configured
```

测试内容：
- ✅ 模型列表端点返回格式
- ✅ 配置 API Key 时包含 GLM 模型
- ✅ 未配置 API Key 时不包含 GLM 模型
- ✅ GLM 模型显示名称正确

## 测试标记

项目使用 pytest 标记来分类测试：

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.e2e` - 端到端测试

运行特定类型的测试：

```bash
pytest -m unit
pytest -m integration
```

## 覆盖率

生成覆盖率报告：

```bash
# 生成 HTML 报告
pytest --cov --cov-report=html

# 查看报告
# Windows: start htmlcov/index.html
# Linux/Mac: open htmlcov/index.html
```

覆盖率目标：**80%**（在 `pyproject.toml` 中配置）

## 测试最佳实践

1. **使用 Mock**：对于外部 API 调用，使用 `unittest.mock` 或 `pytest-mock`
2. **隔离测试**：每个测试应该独立，不依赖其他测试
3. **清晰命名**：测试函数名应该描述测试的内容
4. **AAA 模式**：Arrange（准备）→ Act（执行）→ Assert（断言）

## 常见问题

### 1. 测试失败：找不到模块

确保在项目根目录运行测试：

```bash
cd backend
pytest
```

### 2. 测试失败：数据库连接错误

单元测试使用 Mock，不需要真实数据库。如果集成测试失败，检查 `conftest.py` 中的测试数据库配置。

### 3. 测试失败：API Key 相关

GLM 相关测试使用 Mock，不需要真实的 API Key。如果测试失败，检查 Mock 配置是否正确。

## CI/CD 集成

测试已配置在 `pyproject.toml` 中，可以在 CI/CD 中运行：

```yaml
# GitHub Actions 示例
- name: Run tests
  run: |
    cd backend
    pytest --cov --cov-report=xml
```

## 相关文件

- `pyproject.toml` - pytest 配置
- `conftest.py` - pytest fixtures
- `Makefile` - 测试命令快捷方式
