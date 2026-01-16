# Scripts 目录说明

本目录仅用于存放**工具脚本**，不包含测试代码。

## 目录规范

### ✅ 应该放在这里的脚本

- **部署工具**: 如 `run_sonar_scanner.py`、`check_sonar_env.py`
- **数据库工具**: 如迁移脚本、数据导入导出
- **开发工具**: 如代码生成脚本、配置检查脚本
- **CI/CD 工具**: 如构建脚本、发布脚本

### ❌ 不应该放在这里的脚本

- **测试脚本**: 应放在 `tests/` 目录
- **验证脚本**: 应放在 `tests/` 目录或作为 pytest 测试
- **示例代码**: 应放在 `examples/` 目录或文档中

## 当前脚本

- `check_sonar_env.py` - 检查 SonarCloud 环境配置
- `run_sonar_scanner.py` - 运行 SonarCloud 代码扫描

## 测试相关

所有测试代码应放在 `tests/` 目录：

- **单元测试**: `tests/unit/`
- **集成测试**: `tests/integration/`
- **端到端测试**: `tests/e2e/`

运行测试：

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行特定测试
pytest tests/integration/test_llm_providers.py
```

## LLM 提供商测试

LLM 提供商的测试位于：

- **单元测试**: `tests/unit/core/test_llm_providers.py` - 测试 Provider 类
- **集成测试**: `tests/integration/test_llm_providers.py` - 测试实际 API 调用

如果需要手动测试 LLM 提供商连接，请使用集成测试：

```bash
# 测试所有配置的 LLM 提供商
pytest tests/integration/test_llm_providers.py -v

# 测试特定提供商（需要配置对应 API Key）
pytest tests/integration/test_llm_providers.py::TestLLMProviders::test_deepseek_chat -v
```
