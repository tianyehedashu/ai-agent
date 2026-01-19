# AI Agent 沙箱镜像

功能强大且轻量的 Docker 镜像，专为 AI Agent 代码执行环境设计。

## 📦 特性

### 内置工具

#### System Tools (BusyBox)
Alpine 自带 busybox，包含 100+ Unix 工具：
- **文件操作**: `cat`, `ls`, `cp`, `mv`, `rm`, `mkdir`, `chmod`, `find`, `grep`, `sed`, `awk`
- **文本处理**: `head`, `tail`, `wc`, `sort`, `uniq`, `cut`, `paste`
- **压缩工具**: `tar`, `gzip`, `gunzip`, `bzip2`, `xz`
- **网络工具**: `wget`, `nc` (netcat)

#### 额外安装的工具
- **Shell**: `bash` (更强大的 shell)
- **版本控制**: `git`
- **HTTP 客户端**: `curl`, `wget`
- **文本编辑器**: `vim`, `nano`
- **JSON 处理**: `jq`
- **目录树**: `tree`
- **进程监控**: `htop`
- **SSH 客户端**: `openssh-client`
- **压缩工具**: `zip`, `unzip`
- **系统工具**: `procps`, `coreutils`, `util-linux`

#### Python 环境
- **Python 3.11** (Alpine 版本)
- **预装包**: `requests`, `ipython`

## 📏 镜像大小

- **基础镜像**: `python:3.11-alpine` (~150MB)
- **最终镜像**: ~200-250MB

## 🚀 使用方法

### 构建镜像

**Linux/Mac:**
```bash
cd backend/docker/sandbox
./build.sh
```

**Windows:**
```powershell
cd backend/docker/sandbox
.\build.ps1
```

**手动构建:**
```bash
docker build -t ai-agent-sandbox:latest -f backend/docker/sandbox/Dockerfile backend/docker/sandbox
```

### 测试镜像

```bash
# 进入容器测试
docker run -it --rm ai-agent-sandbox:latest bash

# 测试 busybox 工具
busybox --list

# 测试 Python
python --version

# 测试常用命令
git --version
curl --version
jq --version
```

### 在配置中使用

#### TOML 配置
```toml
# config/environments/docker-dev.toml
[sandbox.docker]
image = "ai-agent-sandbox:latest"
session_enabled = true
```

#### 代码配置
```python
from core.config.execution_config import (
    DockerConfig,
    ExecutionConfig,
    SandboxConfig,
    SandboxMode,
)

config = ExecutionConfig(
    sandbox=SandboxConfig(
        mode=SandboxMode.DOCKER,
        docker=DockerConfig(
            image="ai-agent-sandbox:latest",
            session_enabled=True,
        ),
    ),
)
```

## 🛠️ 自定义镜像

如需添加更多工具，修改 `Dockerfile`：

```dockerfile
# 添加 Node.js
RUN apk add --no-cache nodejs npm

# 添加 Go
RUN apk add --no-cache go

# 添加更多 Python 包
RUN pip install --no-cache-dir pandas numpy matplotlib
```

## 🔒 安全特性

- 基于 Alpine Linux（最小化攻击面）
- 可选的非 root 用户运行
- 资源限制支持（通过 Docker 配置）
- 网络隔离支持

## 📋 BusyBox 工具列表

完整列表可通过以下命令查看：
```bash
docker run --rm ai-agent-sandbox:latest busybox --list
```

常用工具示例：
- `busybox sh` - Shell
- `busybox ls` - 列出文件
- `busybox grep` - 文本搜索
- `busybox awk` - 文本处理
- `busybox tar` - 归档工具

## 🎯 使用场景

✅ **适合**:
- AI Agent 代码执行
- 数据处理脚本
- 系统工具调用
- 文件操作
- 网络请求

❌ **不适合**:
- 图形界面应用
- 大量并发计算
- 需要特定硬件加速的场景

## 📝 维护

### 更新 Python 版本
修改 Dockerfile 中的基础镜像：
```dockerfile
FROM python:3.12-alpine  # 升级到 3.12
```

### 清理缓存
```bash
docker system prune -a
```
