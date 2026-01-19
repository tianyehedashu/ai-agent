# Docker 容器输出编码问题修复

## 问题描述

在使用 `run_shell` 工具执行命令（如 `curl wttr.in`）时，返回的输出出现乱码，例如：
```
not found: 鉀咃笍 +0掳C
```

实际应该是：
```
not found: ⛅️  +0°C
```

## 根本原因

1. **Windows 系统编码问题**：在 Windows 上，`subprocess.run` 使用 `text=True` 时，默认使用系统编码（通常是 GBK/CP936），而不是 UTF-8。

2. **容器环境变量缺失**：Docker 容器内没有设置 UTF-8 环境变量（`LANG` 和 `LC_ALL`），导致容器内程序输出可能使用错误的编码。

3. **编码不匹配**：当容器返回 UTF-8 编码的输出（包含 emoji、特殊字符等）时，Windows 系统用 GBK 解码，导致乱码。

## 修复方案

### 1. 在所有 `subprocess.run` 调用中明确指定 UTF-8 编码

修改位置：
- `DockerExecutor._run_container()` (第 209 行)
- `SessionDockerExecutor._exec_in_container()` (第 571 行)
- `SessionDockerExecutor.start_session()` (第 490 行)
- `LocalExecutor._run_subprocess_sync()` (第 710 行)
- `SessionDockerExecutor.cleanup_orphaned_containers()` (第 330 行)
- `SessionDockerExecutor.cleanup_all_session_containers()` (第 408 行)

修复方式：
```python
result = subprocess.run(
    cmd,
    capture_output=True,
    timeout=timeout,
    text=True,
    encoding="utf-8",        # 明确指定 UTF-8 编码
    errors="replace",        # 替换无法解码的字符，避免崩溃
    check=False,
)
```

### 2. 在 Docker 容器中设置 UTF-8 环境变量

#### 2.1 在运行时通过 docker 命令参数设置（代码层面）

修改位置：
- `DockerExecutor._build_docker_command()` (第 172-175 行)
- `SessionDockerExecutor.start_session()` (第 470-472 行)
- `SessionDockerExecutor._exec_in_container()` (第 556-565 行)

修复方式：
```python
# 在 docker run 命令中添加环境变量
cmd.extend(["-e", "LANG=C.UTF-8"])
cmd.extend(["-e", "LC_ALL=C.UTF-8"])

# 在 docker exec 命令中添加环境变量
cmd = [
    "docker",
    "exec",
    "-w",
    self.container_workspace,
    "-e",
    "LANG=C.UTF-8",
    "-e",
    "LC_ALL=C.UTF-8",
    container_name,
    "sh",
    "-c",
    command,
]
```

#### 2.2 在 Dockerfile 中设置默认环境变量（镜像层面）

修改位置：
- `backend/docker/sandbox/Dockerfile` - 沙箱执行镜像
- `backend/Dockerfile` - 主应用镜像（可选，保持一致性）

修复方式：
```dockerfile
# 设置环境变量（包括 UTF-8 编码支持）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/workspace/bin:$PATH" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
```

**说明**：
- 对于 Alpine Linux 镜像：`C.UTF-8` locale 通常已经可用，无需额外安装
- 对于 Debian/Ubuntu 镜像：`C.UTF-8` locale 通常已经可用，如需 `en_US.UTF-8` 可安装 `locales` 包
- 在 Dockerfile 中设置环境变量可以确保即使没有通过 `-e` 参数传递，容器内也有正确的编码设置

## 修复效果

修复后，所有通过 Docker 容器执行的命令输出都会：
1. 在容器内使用 UTF-8 编码输出
2. 在 Python 代码中正确使用 UTF-8 解码
3. 正确显示 emoji、特殊字符等 Unicode 字符

## 测试建议

可以使用以下命令测试修复是否生效：

```bash
# 测试天气 API（包含 emoji）
curl -s "wttr.in/Beijing?format=3"

# 测试包含特殊字符的输出
echo "测试：中文、emoji ⛅️、特殊符号 °C"
```

预期输出应该正确显示所有字符，不再出现乱码。

## 相关文件

- `backend/core/sandbox/executor.py` - 主要修复文件（代码层面）
- `backend/docker/sandbox/Dockerfile` - 沙箱镜像 Dockerfile（镜像层面）
- `backend/Dockerfile` - 主应用镜像 Dockerfile（可选，保持一致性）

## 注意事项

1. **重新构建镜像**：修改 Dockerfile 后，需要重新构建镜像才能生效：
   ```bash
   # 构建沙箱镜像
   docker build -t ai-agent-sandbox:latest -f backend/docker/sandbox/Dockerfile backend/docker/sandbox/
   
   # 或使用 docker-compose 重新构建
   docker-compose build
   ```

2. **双重保障**：代码层面（通过 `-e` 参数）和镜像层面（Dockerfile ENV）都设置环境变量，确保无论哪种情况都能正确工作。

3. **Alpine vs Debian**：
   - Alpine Linux 使用 musl libc，locale 支持有限，但 `C.UTF-8` 可用
   - Debian/Ubuntu 使用 glibc，locale 支持更完整，`C.UTF-8` 和 `en_US.UTF-8` 都可用
