# Higress 接入 AI Agent

公网示例：`http://gateway.giimallai.com/ai-agent/`（站点根 `/` 为其他系统，勿与 AI Agent 混淆）。

## 探测结果（2026-05）

| 检查项 | 结果 |
|--------|------|
| `GET /ai-agent/api/v1/system/health` | 200，`environment: production` |
| `GET /ai-agent/` | 200，AI Agent SPA |
| `POST /ai-agent/api/v1/chat`（无 Token） | 401，需登录 |
| `https://gateway.giimallai.com/...` | **443 未连通** — 浏览器若强制 HTTPS 会出现 network error |

## 必配项

1. **路径**：`path: /ai-agent`，`pathType: Prefix` → `frontend:80`（见 [`ai-agent-ingress.example.yaml`](ai-agent-ingress.example.yaml)）。
2. **禁止**把 `/ai-agent` rewrite 掉，否则 FastAPI `ROOT_PATH=/ai-agent` 会 404。
3. **SSE 超时**：`higress.io/timeout: "3600"`；云 SLB 空闲超时同步调大。
4. **勿**对 Chat 开启 `proxy-next-upstream` 重试。
5. **前端**：生产构建勿设置 `VITE_API_URL`（同域相对路径 `/ai-agent/api/v1/...`）。

## 验证

```bash
curl -s http://gateway.giimallai.com/ai-agent/api/v1/system/health
# 期望 JSON status healthy

curl -s -o /dev/null -w '%{http_code}\n' http://gateway.giimallai.com/ai-agent/
# 期望 200
```

## 用户访问入口

- 正确：`http://gateway.giimallai.com/ai-agent/`
- 错误：`http://gateway.giimallai.com/`（吉喵云多租户系统，非本应用）

## 相关文档

- [deploy/k8s/README.md](../k8s/README.md)
- [Higress Ingress 注解](https://higress.cn/docs/latest/user/annotation/)
