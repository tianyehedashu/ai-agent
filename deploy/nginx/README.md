# Nginx 配置说明

| 文件 | 用途 |
|------|------|
| [`../../frontend/nginx.conf`](../../frontend/nginx.conf) | Docker 前端镜像内置配置（上游 `backend:8000`） |
| [`ai-agent.bare-metal.conf.example`](ai-agent.bare-metal.conf.example) | 前后端分离 · 裸机 Nginx 示例（上游改为内网 IP/域名） |

## 路径约定

- 默认服务前缀：`/ai-agent`（与 `ROOT_PATH`、`VITE_APP_ROOT` 一致）
- 前端构建产物在磁盘根目录（`index.html`、`assets/`），浏览器 URL 带 `/ai-agent/` 前缀
- **须用 `rewrite` 去掉 URL 前缀后再 `try_files`**，不能直接用 `root` + `/ai-agent/index.html`

## 无前缀部署

将 `ROOT_PATH=`、`VITE_APP_ROOT=` 设为空后，参考 `frontend/nginx.conf` 底部注释块，或把 `location ^~ /ai-agent/` 改为 `location /`。
