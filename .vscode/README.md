# 编辑器配置说明

本目录包含 VSCode/Cursor 编辑器配置，确保编辑器与项目的 lint 配置保持一致。

## 配置内容

### settings.json
- **Ruff 配置**：使用 `backend/pyproject.toml` 中的配置
- **Pylint 配置**：使用 `backend/.pylintrc` 中的配置
- **同时启用 Ruff 和 Pylint**：与项目 `Makefile` 的 `check` 命令保持一致

### extensions.json
推荐安装的扩展列表，确保团队成员使用相同的工具。

## 与项目 Makefile 的一致性

编辑器配置与项目 Makefile 保持一致：

| 命令 | 编辑器行为 |
|------|-----------|
| `make lint` | Ruff 检查（实时显示） |
| `make lint-pylint` | Pylint 检查（实时显示） |
| `make check` | Ruff + Pylint（实时显示） |

## 使用说明

1. **安装推荐扩展**：
   - 打开命令面板（Ctrl+Shift+P）
   - 运行 "Extensions: Show Recommended Extensions"
   - 安装所有推荐的扩展

2. **验证配置**：
   - 打开任意 Python 文件
   - 应该能看到 Ruff 和 Pylint 的诊断信息
   - 保存文件时自动格式化（使用 Ruff）

3. **如果编辑器没有使用项目配置**：
   - 检查是否安装了 Ruff 和 Pylint 扩展
   - 重启编辑器
   - 检查工作区设置是否覆盖了用户设置

## 配置同步

如果修改了以下文件，需要同步更新编辑器配置：

- `backend/pyproject.toml` - Ruff 配置
- `backend/.pylintrc` - Pylint 配置
- `backend/Makefile` - lint 命令

编辑器会自动读取这些配置文件，无需手动更新 `.vscode/settings.json`。
