# Workspace 目录删除指南

## 目录用途分析

### 1. 当前状态
- `backend/workspace` 目录包含：
  - 示例文件（`hello.py`, `test.txt` 等）
  - 测试文件（`second_test.txt`, `user_profile.txt` 等）
  - `langgraph_agent/` 子项目（示例项目）
  - 配置文件（`.env.example`, `config.json` 等）
  - 文档（`README.md`）

### 2. 代码依赖情况

#### 配置项引用
- `backend/app/config.py` 中有 `work_dir: str = "./workspace"` 配置项
- 此配置在以下场景使用：
  - **LocalExecutor 模式**：作为本地执行的工作目录
  - **文件工具**（`file_tools.py`）：作为相对路径的基础路径
  - **代码工具**（`code_tools.py`）：作为代码搜索的基础路径

#### 实际使用场景
- **Docker 模式**（当前默认）：
  - 工具在容器内执行，使用容器内的工作目录（`/workspace`）
  - **不使用**主机的 `./workspace` 目录
  - 每个会话有独立的临时目录

- **Local 模式**（开发/测试）：
  - 工具在主机上执行
  - 使用 `settings.work_dir`（即 `./workspace`）作为工作目录
  - **需要**此目录存在

## 删除建议

### 方案 A：完全删除（推荐，如果只使用 Docker 模式）

**适用场景**：
- 生产环境只使用 Docker 沙箱
- 不需要本地执行模式

**操作步骤**：
```bash
# 删除整个目录
rm -rf backend/workspace

# 或者保留空目录结构（如果需要）
mkdir -p backend/workspace
touch backend/workspace/.gitkeep
```

**注意事项**：
- 如果将来需要使用 Local 模式，需要重新创建目录
- 配置项 `work_dir` 可以改为其他路径（如 `/tmp/workspace`）

### 方案 B：清理内容，保留目录（推荐，如果需要兼容 Local 模式）

**适用场景**：
- 可能需要使用 Local 模式进行开发/测试
- 需要保留目录结构

**操作步骤**：
```bash
# 删除目录内容，保留结构
cd backend/workspace
rm -rf api/ langgraph_agent/ src/
rm -f *.py *.txt *.json *.c Makefile project_id.txt file_list.txt
# 保留 README.md 和 .env.example（如果需要）
```

**保留的文件**：
- `README.md`（如果需要文档）
- `.env.example`（如果需要示例配置）

### 方案 C：移动到其他位置（推荐，如果需要保留示例）

**适用场景**：
- 想保留示例代码作为参考
- 但不想在项目根目录

**操作步骤**：
```bash
# 移动到 docs 或 examples 目录
mkdir -p docs/examples
mv backend/workspace docs/examples/workspace-examples
```

## 推荐方案

**推荐使用方案 A（完全删除）**，原因：

1. ✅ **当前使用 Docker 模式**：不需要主机上的 workspace 目录
2. ✅ **已被 gitignore 忽略**：目录中的文件不会被提交
3. ✅ **运行时自动创建**：如果需要，可以在运行时创建临时目录
4. ✅ **简化项目结构**：减少不必要的目录

## 实施步骤

### 1. 删除目录
```bash
# Windows PowerShell
Remove-Item -Recurse -Force backend\workspace

# 或者保留空目录
New-Item -ItemType Directory -Path backend\workspace -Force
```

### 2. 更新配置（可选）
如果需要支持 Local 模式，可以修改配置使用临时目录：

```python
# backend/app/config.py
work_dir: str = "/tmp/workspace"  # 或使用环境变量
```

### 3. 更新 .gitignore（如果需要）
确保 workspace 目录被忽略：
```
backend/workspace/
```

## 验证

删除后验证：
1. ✅ Docker 模式仍然正常工作（使用容器内工作目录）
2. ✅ 如果使用 Local 模式，确保工作目录存在或配置正确
3. ✅ 没有代码直接导入 `backend/workspace` 中的文件

## 总结

- **可以安全删除**：如果只使用 Docker 模式
- **建议删除**：简化项目结构，避免混淆
- **保留目录结构**：如果将来可能需要 Local 模式
