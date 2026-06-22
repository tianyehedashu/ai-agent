---
name: k8s-production-debug
description: >-
  Debug ai-agent production on Alibaba Cloud K8s (wuhan-ali ops host): API 404/502,
  ROOT_PATH/nginx mismatch, Secret env typos, backend pod restarts. Use when
  production returns 404 on /ai-agent/api/*, deploying to test namespace,
  kubectl on wuhan-ali, or verifying frontend/backend after K8s rollout.
disable-model-invocation: true
---

# AI Agent K8s 生产环境调试

## 环境速查

| 项 | 值 |
|----|-----|
| SSH 跳板 | `ssh wuhan-ali`（用户 `tangqi@ops`） |
| Namespace | `test` |
| **公网入口（当前）** | **`https://gateway.giimallai.com/ai-agent/`** |
| HiGress LB | `8.136.34.39`（`higress-gateway` LoadBalancer） |
| 服务 | `frontend`（Nginx+静态 ClusterIP）、`backend`（FastAPI:8000 ClusterIP） |
| HiGress Ingress | `ai-agent-api`（`/ai-agent/api/*` → backend）、`ai-agent-spa`（`/ai-agent` → frontend） |
| 后端 Secret | `ai-agent-backend-env` |
| 镜像 | `giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/{test,prod}/ai-agent-{backend,frontend}:TAG` |

> **已废弃**：`121.40.54.65` 旧 frontend LoadBalancer 已从集群移除；该 IP 仅返回 SPA HTML，**API 不可用**。勿再用此 IP 探测。

### 流量路径

```
浏览器
  → gateway.giimallai.com（HiGress 8.136.34.39）
      ├─ /ai-agent/api/*  → ai-agent-api Ingress → backend:8000
      └─ /ai-agent/*      → ai-agent-spa Ingress → frontend Nginx
                              └─ /ai-agent/api/* 再反代 → backend:8000
```

## 第一步：区分 404 来源

```bash
curl.exe -s https://gateway.giimallai.com/ai-agent/api/v1/auth/me
curl.exe -sI https://gateway.giimallai.com/ai-agent/api/v1/auth/me
```

| 响应 | 含义 |
|------|------|
| `{"detail":"Not Found"}` + `Content-Type: application/json` | **FastAPI 404**（请求已到 backend，路由未匹配） |
| HTML `<title>404 Not Found</title>` + `Server: nginx` | **Nginx 404**（未反代或 location 错误） |
| `401` / `{"detail":"Authentication required"}` | 路由正常，鉴权问题（**不是路径 bug**） |
| `200` + HTML（Vite App） | 误打到 SPA（旧 IP `121.40.54.65` 或 `/ai-agent/health` 被静态 location 吃掉） |
| `502` / `503` | backend Pod 未 Ready 或 upstream 不可达 |

**勿用** `/ai-agent/health` 判断后端——会返回前端 `index.html`。应测：

```bash
curl.exe -s https://gateway.giimallai.com/ai-agent/api/v1/system/health
curl.exe -s -o NUL -w "%{http_code}\n" https://gateway.giimallai.com/ai-agent/api/v1/system/health
```

## 标准排查流程

```
- [ ] 1. 公网探测（gateway.giimallai.com，上表）
- [ ] 2. 集群 Pod/Service 状态（RESTARTS、Ready）
- [ ] 3. Pod 内直连 backend
- [ ] 4. 经 frontend Nginx 转发
- [ ] 5. 检查 ROOT_PATH / openapi 注册路径
- [ ] 6. 若反复重启 → 查探针 / 连接池 / previous logs
- [ ] 7. 修复 Secret 或配置 → rollout restart
- [ ] 8. 公网复验
```

### 2. 集群状态

```bash
ssh wuhan-ali "kubectl -n test get pod,svc"
ssh wuhan-ali "kubectl -n test get pod -l app=backend -o wide"
ssh wuhan-ali "kubectl -n test logs deployment/backend --tail=50"
ssh wuhan-ali "kubectl -n test logs deployment/frontend --tail=30"
```

`kubectl exec` 须用 `--`：

```bash
kubectl -n test exec backend-POD -- curl -s http://127.0.0.1:8000/health
```

### 3. Pod 内直连 backend（定位路由 vs 反代）

```bash
BPOD=$(ssh wuhan-ali "kubectl -n test get pod -l app=backend -o jsonpath='{.items[0].metadata.name}'")

ssh wuhan-ali "kubectl -n test exec $BPOD -- curl -s http://127.0.0.1:8000/health"
ssh wuhan-ali "kubectl -n test exec $BPOD -- curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/ai-agent/api/v1/auth/me"
ssh wuhan-ali "kubectl -n test exec $BPOD -- curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/v1/auth/me"
```

- 两者都 404 → **backend 路由注册问题**（常见 ROOT_PATH）
- 仅带 `/ai-agent` 前缀的路径 404 → **ROOT_PATH 与 Nginx 不一致**
- Pod 内 200/401、公网 404/502 → **HiGress 路由或 frontend Nginx**

### 4. 经 frontend 转发

```bash
FPOD=$(ssh wuhan-ali "kubectl -n test get pod -l app=frontend -o jsonpath='{.items[0].metadata.name}'")

ssh wuhan-ali "kubectl -n test exec $FPOD -- curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/ai-agent/api/v1/auth/me"
ssh wuhan-ali "kubectl -n test exec $FPOD -- cat /etc/nginx/conf.d/default.conf"
```

仓库参考：`frontend/nginx.conf`、`deploy/nginx/ai-agent.bare-metal.conf.example`、`deploy/higress/README.md`

### 5. ROOT_PATH 检查（高频根因）

```bash
# 环境变量（注意尾随空格）
ssh wuhan-ali "kubectl -n test exec $BPOD -- env | grep ROOT_PATH"

# Secret 原始字节（必须无尾随 0x20）
ssh wuhan-ali "kubectl -n test get secret ai-agent-backend-env -o jsonpath='{.data.ROOT_PATH}' | base64 -d | xxd"
# 正确: 2f61 692d 6167 656e 74  →  /ai-agent
# 错误: 2f61 692d 6167 656e 7420 →  /ai-agent␠
```

**典型故障**：Secret 中 `ROOT_PATH=/ai-agent ` 带空格 → OpenAPI 注册为 `/ai-agent /api/v1/auth/me`（路径含空格），而 Nginx/前端请求 `/ai-agent/api/v1/auth/me` → 全 API 404。

验证空格路径：

```bash
ssh wuhan-ali "kubectl -n test exec $BPOD -- curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8000/ai-agent%20/api/v1/auth/me'"
# 若 %20 版返回 401、无空格版 404 → 确认 ROOT_PATH 尾随空格
```

拉 openapi 看注册路径（在 wuhan-ali 上执行后 scp 解析，避免 Windows SSH 引号问题）：

```bash
ssh wuhan-ali "kubectl -n test exec $BPOD -- curl -s http://127.0.0.1:8000/openapi.json > /tmp/openapi.json"
scp wuhan-ali:/tmp/openapi.json /tmp/openapi-k8s.json
python -c "import json;d=json.load(open('/tmp/openapi-k8s.json'));print([p for p in d['paths'] if 'auth/me' in p])"
# 正常: ['/ai-agent/api/v1/auth/me']
# 异常: ['/ai-agent /api/v1/auth/me']
```

### 6. Backend Pod 反复重启

```bash
ssh wuhan-ali "kubectl -n test describe pod -l app=backend | grep -E 'Restart|Exit|Last State|Unhealthy|OOM'"
ssh wuhan-ali "kubectl -n test logs deployment/backend --previous --tail=80"
```

| 信号 | 含义 | 常见根因 |
|------|------|----------|
| `Exit Code: 137` + Liveness `context deadline exceeded` | kubelet **SIGKILL**（探活杀容器） | 事件循环被阻塞，`/health` 无法及时响应 |
| `QueuePool limit ... connection timed out`（previous logs） | **PostgreSQL 连接池耗尽** | 4 workers × (pool 20+overflow 10)；高并发或慢 SQL |
| `Readiness probe failed` 启动期持续 | 启动过慢 | MCP 初始化、多 worker 冷启动；考虑 `startupProbe` |
| `OOMKilled` | 内存超限 | 4Gi limit 不够；查 `dmesg` / 内存 profile |

**与 Redis/DB 网络的关系**：连接池超时 ≠ 网络不通。先用 Pod 内脚本验证连通性（见 [reference.md](reference.md) §连通性探测）。

/config 注释（`bootstrap/config.py`）：Redis 不可用时配额回退 DB，会放大连接池压力 → 更易触发探活超时重启。

## 修复：ROOT_PATH Secret

```bash
# 正确 base64（无换行/空格）
echo -n /ai-agent | base64   # → L2FpLWFnZW50
```

用 patch 文件（避免 shell 转义）：

```json
{"data":{"ROOT_PATH":"L2FpLWFnZW50"}}
```

```bash
scp patch-root-path.json wuhan-ali:/tmp/patch-root-path.json
ssh wuhan-ali "kubectl -n test patch secret ai-agent-backend-env --type=merge --patch-file /tmp/patch-root-path.json"
ssh wuhan-ali "kubectl -n test rollout restart deployment/backend"
ssh wuhan-ali "kubectl -n test rollout status deployment/backend --timeout=180s"
```

## 修复后验证

```bash
curl.exe -s https://gateway.giimallai.com/ai-agent/api/v1/auth/me          # 期望 401 或 200，非 404/HTML
curl.exe -s -o NUL -w "%{http_code}\n" https://gateway.giimallai.com/ai-agent/api/v1/system/health  # 期望 200 JSON
```

## 其他常见原因

| 现象 | 方向 |
|------|------|
| 全 API 404，/health 200 | ROOT_PATH 空格或未生效；重启 backend |
| 公网 502，Pod 内正常 | backend Not Ready；查 RESTARTS 与探针 |
| 公网 200+HTML 当 API | 打到废弃 IP `121.40.54.65` 或 HiGress 路由优先级错误 |
| 502 Bad Gateway | backend Pod 未 Ready；查 `kubectl logs` |
| Chat 500 但 health 正常 | LiteLLM 模型映射、配额耗尽等业务错误 |
| 8000 公网超时 | 正常，backend 仅 ClusterIP，勿直连 |

## Windows 本地注意

- 用 `curl.exe`，不用 PowerShell 的 `curl` 别名
- 复杂 `kubectl exec` / JSON patch 优先 **scp 脚本到 wuhan-ali 再执行**，避免引号被 PowerShell 吃掉

## 延伸阅读

- HiGress 入口：[deploy/higress/README.md](../../../deploy/higress/README.md)
- 部署文档：[docs/deployment-production.html](../../../docs/deployment-production.html)
- K8s 清单：[backend/Deployment.yaml](../../../backend/Deployment.yaml)、[frontend/Deployment.yaml](../../../frontend/Deployment.yaml)
- 命令与决策树：[reference.md](reference.md)
