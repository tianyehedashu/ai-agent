# K8s 生产调试 — 命令参考

## 一键采集（在 wuhan-ali 上）

```bash
NS=test
BPOD=$(kubectl -n $NS get pod -l app=backend -o jsonpath='{.items[0].metadata.name}')
FPOD=$(kubectl -n $NS get pod -l app=frontend -o jsonpath='{.items[0].metadata.name}')

echo "=== pods ==="
kubectl -n $NS get pod -l 'app in (backend,frontend)'

echo "=== backend env ==="
kubectl -n $NS exec $BPOD -- env | grep -E 'ROOT_PATH|APP_ENV|DEBUG'

echo "=== ROOT_PATH bytes ==="
kubectl -n $NS get secret ai-agent-backend-env -o jsonpath='{.data.ROOT_PATH}' | base64 -d | xxd

echo "=== backend curls ==="
kubectl -n $NS exec $BPOD -- curl -s -o /dev/null -w 'health:%{http_code}\n' http://127.0.0.1:8000/health
kubectl -n $NS exec $BPOD -- curl -s -o /dev/null -w 'prefixed auth/me:%{http_code}\n' http://127.0.0.1:8000/ai-agent/api/v1/auth/me
kubectl -n $NS exec $BPOD -- curl -s -o /dev/null -w 'bare auth/me:%{http_code}\n' http://127.0.0.1:8000/api/v1/auth/me
kubectl -n $NS exec $BPOD -- curl -s -o /dev/null -w 'space auth/me:%{http_code}\n' 'http://127.0.0.1:8000/ai-agent%20/api/v1/auth/me'

echo "=== frontend proxy ==="
kubectl -n $NS exec $FPOD -- curl -s -o /dev/null -w 'via nginx:%{http_code}\n' http://127.0.0.1/ai-agent/api/v1/auth/me
```

## 决策树

```
API 404?
├─ 响应是 JSON {"detail":"Not Found"}
│  ├─ Pod 内 /ai-agent/api/* 也 404
│  │  ├─ /ai-agent%20/api/* → 401  → ROOT_PATH 尾随空格 → patch Secret
│  │  ├─ openapi 路径含空格        → 同上
│  │  └─ openapi 无 api 路由       → 镜像过旧 / 启动失败，查 logs
│  └─ Pod 内 OK、公网 404          → frontend nginx.conf / 镜像
└─ 响应是 nginx HTML               → location / proxy_pass 未匹配
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

## 本次 incident 摘要（2026-05）

- **症状**：`GET /ai-agent/api/v1/auth/me` → 404
- **根因**：`ai-agent-backend-env` 中 `ROOT_PATH` base64 解码为 `/ai-agent `（尾随空格）
- **修复**：patch 为 `L2FpLWFnZW50`，rollout restart backend
- **验证**：公网 auth/me → 401；system/health → 200
