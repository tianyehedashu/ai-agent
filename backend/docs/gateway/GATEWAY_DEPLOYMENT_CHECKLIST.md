# Gateway 生产部署清单（第三方客户端 / 长连接）

## 反向代理（nginx / Higress）

```nginx
client_max_body_size 50m;
proxy_read_timeout 600s;
proxy_send_timeout 600s;
proxy_buffering off;          # SSE 必须关闭缓冲
proxy_http_version 1.1;
proxy_set_header Connection "";
keepalive_timeout 75s;
```

Higress Ingress 须显式加长超时（含**非流式** chat/completions，否则外层默认 ~60s 会 504）：

```yaml
metadata:
  annotations:
    higress.io/timeout: "3600"
```

若仍见 `504` 且耗时恰好 ~60000ms，检查 SLB / 外层 Nginx 是否仍有 60s 默认读超时。

## uvicorn

```bash
uvicorn bootstrap.main:app --host 0.0.0.0 --port 8000 \
  --timeout-keep-alive 120 \
  --limit-max-requests 0
```

## 验证

1. **5 分钟流式**：`curl -N .../v1/chat/completions` 与 `.../v1/messages`，`stream=true`
2. **大 body**：≥ 100KB JSON messages（长上下文场景）
3. **双协议鉴权**：Bearer 与 `x-api-key` 各测一次
4. **Claude Code count_tokens**：`POST /v1/messages/count_tokens` 返回 `{"input_tokens":N}`

## TLS

- HTTP/1.1 与 HTTP/2 均需验证 SSE；部分客户端默认 HTTP/1.1 长连接。

## Redis

- `gateway_router_redis_url` 或全局 `redis_url` 可用（限流与 Router 状态）。
