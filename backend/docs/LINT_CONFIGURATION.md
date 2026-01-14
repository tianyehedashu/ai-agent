# Lint 配置说明

本文档说明项目的 lint 配置，确保编辑器和命令行工具使用相同的配置。

## 配置一致性

### 命令行工具（Makefile）

```bash
make lint          # 运行 Ruff 检查
make lint-pylint   # 运行 Pylint 检查
make check         # 运行 Ruff + Pylint + 类型检查
```

### 编辑器配置（VSCode/Cursor）

编辑器配置位于 `.vscode/settings.json`，确保：

1. **Ruff** 使用 `backend/pyproject.toml` 配置
2. **Pylint** 使用 `backend/.pylintrc` 配置
3. **同时启用** Ruff 和 Pylint（与 `make check` 一致）

## 配置文件位置

| 工具 | 配置文件 | 说明 |
|------|---------|------|
| Ruff | `backend/pyproject.toml` | Ruff linting 和格式化规则 |
| Pylint | `backend/.pylintrc` | Pylint 检查规则 |
| 编辑器 | `.vscode/settings.json` | VSCode/Cursor 编辑器配置 |

## 为什么需要两个工具？

### Ruff
- ✅ 速度快，适合实时检查
- ✅ 支持自动修复
- ✅ 检查 pycodestyle、Pyflakes 等规则

### Pylint
- ✅ 深度代码分析
- ✅ 检查架构和设计问题
- ✅ 检查 Pylint 特有的规则（C 系列规则）

### 互补关系

| 规则类型 | Ruff | Pylint | 说明 |
|---------|------|--------|------|
| `C0413` (wrong-import-position) | ❌ | ✅ | 检测导入位置错误 |
| `C0415` (import-outside-toplevel) | ❌ | ✅ | **检测函数内部导入** |
| `E402` (module level import not at top) | ✅ | ✅ | 检测模块级导入不在顶部 |
| `I001` (isort) | ✅ | ❌ | 检测导入排序和组织 |
| `C0116` (missing-function-docstring) | ❌ | ✅ | 检测缺少函数文档 |
| `C0301` (line-too-long) | ✅ (E501) | ✅ | 检测行长度 |
| `W0718` (broad-exception-caught) | ✅ (BLE001) | ✅ | 检测过于宽泛的异常捕获 |

## 函数内部导入检测

### 问题说明

根据 PEP 8，导入语句应该放在文件顶部。函数内部导入虽然在某些情况下是合法的（如避免循环导入），但通常应该避免。

### 检测配置

#### 1. Ruff 配置 (`pyproject.toml`)

```toml
[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors (includes E402)
    "I",      # isort (import sorting)
    # ...
]
```

- **E402**: 检测模块级导入不在文件顶部
- **I (isort)**: 检测导入排序和组织问题
- **注意**: Ruff 的 E402 主要检测模块级导入，对函数内部导入的检测有限

#### 2. Pylint 配置 (`.pylintrc`)

```ini
[MESSAGES CONTROL]
# E402 (import-outside-toplevel) 未禁用，会检测函数内部导入
disable=
    # ... 其他规则
    # 注意: 不要禁用 E402
```

- **E402 (import-outside-toplevel)**: Pylint 会检测函数内部的导入语句
- **C0413 (wrong-import-position)**: 检测导入位置错误

### 工程实践建议

1. **默认规则**: 所有导入应放在文件顶部
2. **例外情况**: 仅在以下情况允许函数内部导入：
   - 避免循环导入
   - 延迟导入以加快模块加载（需谨慎使用）
   - 条件导入（仅在特定条件下需要）

3. **检测工具组合**:
   - **Ruff**: 快速检测模块级导入问题
   - **Pylint**: 深度检测函数内部导入
   - **isort**: 自动整理导入顺序

### 示例

❌ **不推荐** - 函数内部导入：
```python
def process_data():
    import yaml  # 应该在文件顶部
    data = yaml.load(...)
```

✅ **推荐** - 文件顶部导入：
```python
import yaml

def process_data():
    data = yaml.load(...)
```

✅ **可接受** - 避免循环导入：
```python
def get_config():
    # 延迟导入以避免循环依赖
    from app.config import settings
    return settings
```

## 验证配置

### 1. 验证编辑器配置

打开任意 Python 文件，应该看到：
- Ruff 的诊断信息（快速检查）
- Pylint 的诊断信息（深度分析）

### 2. 验证命令行配置

```bash
# 在 backend 目录下运行
make lint          # 应该只显示 Ruff 检查结果
make lint-pylint   # 应该只显示 Pylint 检查结果
make check         # 应该显示所有检查结果
```

### 3. 验证配置同步

如果修改了以下文件，编辑器会自动读取新配置：
- `backend/pyproject.toml` - Ruff 配置
- `backend/.pylintrc` - Pylint 配置

## 常见问题

### Q: 编辑器没有显示 Pylint 错误？

A: 检查：
1. 是否安装了 Pylint 扩展
2. 是否安装了 Ruff 扩展
3. 重启编辑器
4. 检查输出面板是否有错误信息

### Q: 编辑器显示的错误与 `make check` 不一致？

A: 确保：
1. 编辑器使用工作区设置（不是用户设置）
2. 配置文件路径正确
3. 扩展已正确安装

### Q: 如何只使用 Ruff？

A: 在 `.vscode/settings.json` 中设置：
```json
{
  "python.linting.pylintEnabled": false
}
```

但建议同时使用两个工具，以获得完整的代码质量检查。

## 更新配置

如果项目需要更新 lint 规则：

1. **更新 Ruff 规则**：修改 `backend/pyproject.toml` 的 `[tool.ruff.lint]` 部分
2. **更新 Pylint 规则**：修改 `backend/.pylintrc` 的 `[MESSAGES CONTROL]` 部分
3. **编辑器会自动读取**：无需修改 `.vscode/settings.json`

## 相关文件

- `backend/Makefile` - 命令行 lint 命令
- `backend/pyproject.toml` - Ruff 配置
- `backend/.pylintrc` - Pylint 配置
- `.vscode/settings.json` - 编辑器配置
- `.vscode/extensions.json` - 推荐扩展列表
