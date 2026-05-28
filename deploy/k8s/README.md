# 阿里云 ACK 生产部署（当前生产环境）

> 运维入口：`ssh wuhan-ali` → `kubectl -n test …`  
> 故障排查 Skill：[`.agents/skills/k8s-production-debug/SKILL.md`](../../.agents/skills/k8s-production-debug/SKILL.md)  
> **Higress 入口**（如 `gateway.giimallai.com`）：[deploy/higress/README.md](../higress/README.md)

## 架构

```
用户浏览器
    │  http://121.40.54.65/ai-agent/
    ▼
frontend Service (LoadBalancer :80)
    │  Pod 内 Nginx：静态 SPA + 反代 /ai-agent/api/
    ▼
backend Service (ClusterIP :8000，不对公网暴露)
    │
    ├── PostgreSQL（阿里云 RDS）
    ├── Redis（阿里云 Redis）
    └── qdrant Service（集群内 Pod）
```

| 资源 | 名称 | 说明 |
|------|------|------|
| Namespace | `test` | ai-agent 工作负载 |
| 公网入口 | `121.40.54.65:80` | frontend LoadBalancer |
| 后端 Secret | `ai-agent-backend-env` | 环境变量（含 `ROOT_PATH`、DB、LLM Key） |
| 镜像仓库 | `giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/` | `ai-agent-backend` / `ai-agent-frontend` |
| 清单 | [`backend/Deployment.yaml`](../../backend/Deployment.yaml)、[`frontend/Deployment.yaml`](../../frontend/Deployment.yaml) | Deployment + Service |

默认路径前缀：`/ai-agent`（`ROOT_PATH`、`VITE_APP_ROOT`、Nginx 三者须一致）。

## 首次部署

### 1. 构建并推送镜像

在 CI 或构建机（需能 push 至 ACR）：

```bash
# 后端
docker build -f backend/Dockerfile -t giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/ai-agent-backend:v1.0.0 backend/
docker push giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/ai-agent-backend:v1.0.0

# 前端（构建参数与 ROOT_PATH 一致）
docker build -f frontend/Dockerfile --build-arg VITE_APP_ROOT=/ai-agent \
  -t giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/ai-agent-frontend:v1.0.0 frontend/
docker push giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/ai-agent-frontend:v1.0.0
```

### 2. 创建 Secret

以 [`deploy/backend.env.production`](../backend.env.production) 为参考，**勿直接 commit 含真实 Key 的文件**。

```bash
kubectl -n test create secret generic ai-agent-backend-env \
  --from-env-file=backend.env.production \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Agent 记忆 / Embedding**（SSE 对话依赖；参考 [`deploy/backend.env.production`](../backend.env.production)）：

```bash
# 检查 Secret 是否含 EMBEDDING_MODEL（缺省会导致流式对话报错）
ssh wuhan-ali "kubectl -n test exec deploy/backend -- env | grep EMBEDDING"
# 若无输出，用 patch 补全后 rollout restart backend
```

```json
{"data":{"EMBEDDING_MODEL":"ZGFzaHNjb3BlL3RleHQtZW1iZWRkaW5nLXYz","EMBEDDING_DIMENSION":"MTAyNA=="}}
```

（`echo -n 'dashscope/text-embedding-v3' | base64` → `ZGFzaHNjb3BlL3RleHQtZW1iZWRkaW5nLXYz`，`echo -n '1024' | base64` → `MTAyNA==`）

**ROOT_PATH 必须无尾随空格**（曾导致全 API 404）：

```bash
echo -n '/ai-agent' | base64   # → L2FpLWFnZW50
kubectl -n test get secret ai-agent-backend-env -o jsonpath='{.data.ROOT_PATH}' | base64 -d | xxd
# 正确末尾: ... 74  （无 20 空格）
```

### 3. 应用清单与 PVC

```bash
# 需事先创建 backend-data-pvc、backend-workspace-pvc（见集群现有配置）
kubectl -n test apply -f backend/Deployment.yaml
kubectl -n test apply -f frontend/Deployment.yaml
```

### 4. 数据库迁移

```bash
BPOD=$(kubectl -n test get pod -l app=backend -o jsonpath='{.items[0].metadata.name}')
kubectl -n test exec $BPOD -- alembic upgrade head
```

### 5. 验证

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://121.40.54.65/ai-agent/api/v1/system/health   # 200
curl -s http://121.40.54.65/ai-agent/api/v1/auth/me   # 401 或 200，非 404
```

勿用 `/ai-agent/health` 测后端——会返回前端 SPA HTML。

## 日常发版

```bash
# 1. 构建 push 新 tag（或更新 Deployment 中 image tag）
# 2. 滚动更新
kubectl -n test set image deployment/backend backend=giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/ai-agent-backend:NEW_TAG
kubectl -n test set image deployment/frontend frontend=giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/ai-agent-frontend:NEW_TAG

# 3. 后端 schema 变更时
kubectl -n test exec deploy/backend -- alembic upgrade head

# 4. 观察 rollout
kubectl -n test rollout status deployment/backend
kubectl -n test rollout status deployment/frontend
```

## 配置变更（Secret）

```json
{"data":{"ROOT_PATH":"L2FpLWFnZW50"}}
```

```bash
kubectl -n test patch secret ai-agent-backend-env --type=merge --patch-file patch.json
kubectl -n test rollout restart deployment/backend
```

## 运维命令

```bash
kubectl -n test get pod,svc
kubectl -n test logs deployment/backend --tail=100 -f
kubectl -n test logs deployment/frontend --tail=50 -f
kubectl -n test exec deploy/frontend -- cat /etc/nginx/conf.d/default.conf
```

## 与 Docker Compose 的差异

| 项 | K8s（生产） | Docker Compose（备选） |
|----|-------------|------------------------|
| 入口 | frontend LoadBalancer | 单机 Nginx / `:3000` |
| 后端暴露 | 仅 ClusterIP | 可映射 `:8000` |
| 环境变量 | Secret `ai-agent-backend-env` | `backend/.env` + `.env.production` |
| 发版 | 镜像 tag + rollout | `make deploy` / `deploy.sh` |
| 文档 | 本文 | [docs/DEPLOYMENT.md](../../docs/DEPLOYMENT.md) §Compose |
