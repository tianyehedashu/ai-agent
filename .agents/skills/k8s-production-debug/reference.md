# K8s 生产调试 — 命令参考

## 公网入口（当前）

| 用途 | URL |
|------|-----|
| 站点 | `https://gateway.giimallai.com/ai-agent/` |
| Health | `https://gateway.giimallai.com/ai-agent/api/v1/system/health` |
| Auth 探针 | `https://gateway.giimallai.com/ai-agent/api/v1/auth/me` |
| HiGress LB | `http://8.136.34.39/ai-agent/...`（等价，无 TLS） |

已废弃：`121.40.54.65`（旧 frontend LB，API 返回 SPA HTML）。

## 一键采集（在 wuhan-ali 上）

```bash
NS=test
BPOD=$(kubectl -n $NS get pod -l app=backend -o jsonpath='{.items[0].metadata.name}')
FPOD=$(kubectl -n $NS get pod -l app=frontend -o jsonpath='{.items[0].metadata.name}')

echo "=== pods ==="
kubectl -n $NS get pod -l 'app in (backend,frontend)'

echo "=== backend restart / probe ==="
kubectl -n $NS describe pod -l app=backend | grep -E 'Restart|Exit|Last State|Unhealthy|OOM'

echo "=== backend env ==="
kubectl -n $NS exec $BPOD -- env | grep -E 'ROOT_PATH|APP_ENV|DEBUG|REDIS_URL|DATABASE_URL'

echo "=== ROOT_PATH bytes ==="
kubectl -n $NS get secret ai-agent-backend-env -o jsonpath='{.data.ROOT_PATH}' | base64 -d | xxd

echo "=== backend curls ==="
kubectl -n $NS exec $BPOD -- curl -s -o /dev/null -w 'health:%{http_code}\n' http://127.0.0.1:8000/health
kubectl -n $NS exec $BPOD -- curl -s -o /dev/null -w 'prefixed auth/me:%{http_code}\n' http://127.0.0.1:8000/ai-agent/api/v1/auth/me
kubectl -n $NS exec $BPOD -- curl -s -o /dev/null -w 'bare auth/me:%{http_code}\n' http://127.0.0.1:8000/api/v1/auth/me
kubectl -n $NS exec $BPOD -- curl -s -o /dev/null -w 'space auth/me:%{http_code}\n' 'http://127.0.0.1:8000/ai-agent%20/api/v1/auth/me'

echo "=== frontend proxy ==="
kubectl -n $NS exec $FPOD -- curl -s -o /dev/null -w 'via nginx:%{http_code}\n' http://127.0.0.1/ai-agent/api/v1/auth/me

echo "=== previous container (if restarted) ==="
kubectl -n $NS logs $BPOD --previous --tail=40 2>/dev/null || true
```

## 连通性探测（Pod 内 Redis / PostgreSQL）

在 wuhan-ali 上执行（脚本放 `/tmp/pod-conn-test.sh`）：

```bash
BPOD=$(kubectl -n test get pod -l app=backend -o jsonpath='{.items[0].metadata.name}')

# TCP
kubectl -n test exec "$BPOD" -- timeout 8 python3 -c "
import socket
for host, port, name in [
    ('test-giimall-redis.redis.rds.aliyuncs.com', 6379, 'Redis'),
    ('prod-giimall-pg.rwlb.rds.aliyuncs.com', 5432, 'PostgreSQL'),
]:
    try:
        s = socket.create_connection((host, port), 5); s.close()
        print(name + ' TCP: OK')
    except Exception as e:
        print(name + ' TCP: FAIL', e)
"

# Redis PING（含 username/password，与 libs/db/redis.py 一致）
kubectl -n test exec "$BPOD" -- timeout 12 python3 -c "
import asyncio, os
from urllib.parse import quote, urlparse
async def main():
    import redis.asyncio as aioredis
    p = urlparse(os.environ['REDIS_URL'])
    u, pw = os.environ.get('REDIS_USERNAME',''), os.environ.get('REDIS_PASSWORD','')
    url = 'redis://' + quote(u) + ':' + quote(pw) + '@' + p.hostname + ':' + str(p.port or 6379) + (p.path or '/0')
    r = aioredis.from_url(url, socket_connect_timeout=5, socket_timeout=5)
    print('Redis PING:', await r.ping()); await r.aclose()
asyncio.run(main())
"

# PostgreSQL SELECT 1
kubectl -n test exec "$BPOD" -- timeout 12 python3 -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def main():
    e = create_async_engine(os.environ['DATABASE_URL'], connect_args={'timeout': 5})
    async with e.connect() as c:
        print('PG SELECT 1:', await c.scalar(text('SELECT 1')))
    await e.dispose()
asyncio.run(main())
"
```

期望：`Redis TCP: OK`、`Redis PING: True`、`PG SELECT 1: 1`。若 TCP OK 但 PING/SELECT 失败 → 凭据或 RDS 白名单；若 previous logs 有 `QueuePool` 而连通性正常 → **连接池耗尽**，非网络断连。

## 决策树

```
API 404?
├─ 响应是 JSON {"detail":"Not Found"}
│  ├─ Pod 内 /ai-agent/api/* 也 404
│  │  ├─ /ai-agent%20/api/* → 401  → ROOT_PATH 尾随空格 → patch Secret
│  │  ├─ openapi 路径含空格        → 同上
│  │  └─ openapi 无 api 路由       → 镜像过旧 / 启动失败，查 logs
│  └─ Pod 内 OK、公网 404/502      → HiGress 路由 / frontend nginx / backend Not Ready
├─ 响应是 nginx HTML（Vite App）   → 废弃 IP 121.40.54.65 或 SPA location 吃掉 API
└─ 502/503                         → backend RESTARTS>0 或 endpoints 空

Pod 反复重启（Exit 137）?
├─ describe 有 Liveness timeout    → 事件循环阻塞，查 previous logs
│  ├─ QueuePool limit reached      → PG 连接池耗尽（4 workers × 30 主池）
│  └─ 启动期 Readiness 失败        → MCP 冷启动慢 → startupProbe / 减 workers
├─ OOMKilled                       → 升 memory limit 或减 workers
└─ Redis/DB TCP 与 PING 均 OK      → 排除网络断连，聚焦池大小与慢 SQL
```

## 路径约定（默认）

| 组件 | 配置 |
|------|------|
| 前端 URL | `/ai-agent/` |
| API | `/ai-agent/api/v1/...` |
| backend `ROOT_PATH` | `/ai-agent`（**无尾随空格**） |
| frontend `VITE_APP_ROOT` | `/ai-agent` |
| Nginx API 反代 | `location /ai-agent/api/` → `proxy_pass http://backend:8000/ai-agent/api/` |
| 探针 | readiness/liveness 用 `/health`（根路径，非 `/ai-agent/health`） |

## Secret 编码规范

```bash
# 正确
echo -n '/ai-agent' | base64

# 错误（会引入换行）
echo '/ai-agent' | base64
```

创建或更新 Secret 后务必：

```bash
kubectl -n test get secret ai-agent-backend-env -o jsonpath='{.data.ROOT_PATH}' | base64 -d | xxd
kubectl -n test rollout restart deployment/backend
```

## Gateway 慢 SQL 基线（EXPLAIN 模板）

在 RDS 或 staging 对高 IO 查询做 `EXPLAIN (ANALYZE, BUFFERS)` 存档，发版前后对比。

```sql
-- 1) 调用统计 GROUP BY（替换时间窗与 tenant_id）
EXPLAIN (ANALYZE, BUFFERS)
SELECT credential_id, COUNT(*), SUM(cost_usd)
FROM gateway_request_logs
WHERE tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
  AND created_at >= NOW() - INTERVAL '7 days'
  AND created_at <= NOW()
GROUP BY credential_id
ORDER BY COUNT(*) DESC
LIMIT 20;

-- 2) Dashboard summary 单行聚合
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(id), SUM(input_tokens), SUM(output_tokens), SUM(cost_usd)
FROM gateway_request_logs
WHERE tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
  AND created_at >= NOW() - INTERVAL '7 days';

-- 3) 日志列表 COUNT（分页总数）
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*)
FROM gateway_request_logs
WHERE tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
  AND created_at >= NOW() - INTERVAL '1 day';

-- 4) hybrid 对照：hourly 历史段
EXPLAIN (ANALYZE, BUFFERS)
SELECT SUM(requests), SUM(cost_usd)
FROM gateway_metrics_hourly
WHERE tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
  AND bucket_at >= date_trunc('hour', NOW() - INTERVAL '7 days')
  AND bucket_at < date_trunc('hour', NOW() - INTERVAL '2 hours');
```

关注：`Partitions pruned`、`Index Scan` vs `Seq Scan`、`Buffers: shared hit/read`。

## Incident 摘要

### 2026-05 — ROOT_PATH 尾随空格

- **症状**：`GET /ai-agent/api/v1/auth/me` → 404
- **根因**：`ai-agent-backend-env` 中 `ROOT_PATH` base64 解码为 `/ai-agent `（尾随空格）
- **修复**：patch 为 `L2FpLWFnZW50`，rollout restart backend

### 2026-06 — Backend 探活杀容器 + 入口迁移

- **症状**：`gateway.giimallai.com` 间歇 502；backend `RESTARTS=1`，`Exit Code 137`
- **根因**：PostgreSQL `QueuePool limit of size 20 overflow 10` → 事件循环阻塞 → Liveness `/health` 超时 → kubelet SIGKILL；非 Redis/PG 网络不通
- **连通性**：Pod 内 Redis PING / PG SELECT 1 均正常（RDS `test-giimall-redis`、`prod-giimall-pg`）
- **入口**：生产已切至 `https://gateway.giimallai.com/ai-agent/`；`121.40.54.65` 已废弃
