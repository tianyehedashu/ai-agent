#!/usr/bin/env python
"""AI Gateway Ops CLI 客户端。

封装 AI Gateway 的 HTTP API 调用，覆盖团队、凭据、模型、路由、配额全流程。
依赖标准库（urllib），无需安装第三方包。

环境变量:
  GATEWAY_BASE_URL   API 基地址，默认 https://gateway.giimallai.com/ai-agent/api/v1（线上）
  GATEWAY_API_KEY    平台 API Key（sk_ 开头，需 gateway:admin 或 gateway:read scope，必需）
  GATEWAY_TOKEN      兼容回退（JWT 或 API Key）；优先使用 GATEWAY_API_KEY

用法:
  python gateway_client.py <category> <command> [options]
  python gateway_client.py --help
  python gateway_client.py teams --help
  python gateway_client.py teams create --name "我的团队"

  注意：--base-url / --token / --raw 是全局参数，必须放在 <category> 之前：
  python gateway_client.py --token sk_xxx teams list
  （错误写法：python gateway_client.py teams list --token sk_xxx）

示例:
  # 仅需设置 API Key（在设置页创建，勾选 gateway_full scope）
  export GATEWAY_API_KEY="sk_xxxxxxxx_xxxxxxxxxxxx"
  python gateway_client.py teams create --name "研发团队"
  python gateway_client.py credentials create --team-id <tid> --provider openai --name main --api-key sk-xxx
  python gateway_client.py credentials probe --team-id <tid> --credential-id <cid>
  python gateway_client.py models batch-import --team-id <tid> --credential-id <cid> --provider openai --items '[{"upstream_model_id":"gpt-4o"}]'
  python gateway_client.py models list --team-id <tid> --all   # 自动翻页拉全部
  python gateway_client.py models test --team-id <tid> --model-id <mid>

  # 便捷模式：为某凭据下全部模型配置每日 480 万 tokens 限额，17:00 重置
  python gateway_client.py quotas batch-upsert --team-id <tid> --credential-id <cid> --limit-tokens 4800000 --all-models --reset-at 17:00

  # 路由共享 / 日志 / 归因
  python gateway_client.py teams find --name-contains "研发"
  python gateway_client.py routes route-grants-publish --target-team-id <tid> --all-routes
  python gateway_client.py proxy models --team-id <tid> --filter volcano
  python gateway_client.py logs get --team-id <tid> --log-id <id> --attribution-only

  # 切换到本地开发环境：
  export GATEWAY_BASE_URL="http://localhost:8000/ai-agent/api/v1"
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "https://gateway.giimallai.com/ai-agent/api/v1"


class GatewayError(Exception):
    """Gateway API 错误。"""

    def __init__(self, status, code, message, details=None, raw=None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
        self.raw = raw
        super().__init__(f"[{status}] {code}: {message}")


def _normalize_api_error(status: int, raw: str) -> GatewayError:
    """解析管理面与 OpenAI 兼容代理的错误体（含 FastAPI detail 嵌套）。"""
    try:
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return GatewayError(status, "HTTP_ERROR", raw or f"HTTP {status}", raw=raw)

    if isinstance(payload.get("error"), dict):
        err = payload["error"]
        return GatewayError(
            status,
            err.get("code", "HTTP_ERROR"),
            err.get("message", raw),
            err.get("details"),
            raw=raw,
        )

    detail = payload.get("detail")
    if isinstance(detail, dict):
        inner = detail.get("error", detail)
        if isinstance(inner, dict):
            message = inner.get("message") or inner.get("type") or json.dumps(inner, ensure_ascii=False)
            return GatewayError(
                status,
                inner.get("code", inner.get("type", "HTTP_ERROR")),
                message,
                inner,
                raw=raw,
            )
        return GatewayError(status, "HTTP_ERROR", str(detail), raw=raw)

    if isinstance(detail, str):
        return GatewayError(status, "HTTP_ERROR", detail, raw=raw)

    return GatewayError(
        status,
        payload.get("code", "HTTP_ERROR"),
        payload.get("message", raw),
        payload.get("details"),
        raw=raw,
    )


class ApiClient:
    """HTTP API 客户端。"""

    def __init__(self, base_url=None, token=None):
        self.base_url = (base_url or os.environ.get("GATEWAY_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        # 优先 GATEWAY_API_KEY，回退 GATEWAY_TOKEN（兼容旧配置）
        self.token = token or os.environ.get("GATEWAY_API_KEY") or os.environ.get("GATEWAY_TOKEN")
        if not self.token:
            sys.stderr.write(
                "错误：未设置 GATEWAY_API_KEY 环境变量。\n"
                "请在设置页创建 API Key（勾选 gateway:admin + gateway:read scope），然后：\n"
                "  export GATEWAY_API_KEY=\"sk_xxxxxxxx_xxxxxxxxxxxx\"\n"
                "或使用 --token 参数传入。\n"
                "（兼容：也可设置 GATEWAY_TOKEN 使用 JWT，但 JWT 会过期）\n"
            )
            sys.exit(2)

    def _request(self, method, path, body=None, params=None):
        url = self.base_url + path
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                from urllib.parse import urlencode
                url = f"{url}?{urlencode(clean)}"

        data = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
                status = resp.status
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise _normalize_api_error(e.code, raw) from e
        except urllib.error.URLError as e:
            raise GatewayError(0, "CONNECTION_ERROR", f"无法连接到 {url}: {e.reason}")

        if not raw:
            return None, status
        try:
            return json.loads(raw), status
        except json.JSONDecodeError:
            return raw, status

    # ---- 通用快捷方法 ----
    def get(self, path, params=None):
        return self._request("GET", path, params=params)[0]

    def post(self, path, body=None, params=None):
        return self._request("POST", path, body=body, params=params)[0]

    def put(self, path, body=None, params=None):
        return self._request("PUT", path, body=body, params=params)[0]

    def patch(self, path, body=None):
        return self._request("PATCH", path, body=body)[0]

    def delete(self, path, params=None):
        return self._request("DELETE", path, params=params)[0]


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def parse_json_arg(value, arg_name):
    """解析 JSON 字符串参数；若不是 JSON 则原样返回字符串。"""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (ValueError, json.JSONDecodeError):
        return value


def print_json(data):
    """美化输出 JSON。"""
    if data is None:
        print("(无响应体)")
        return
    print(json.dumps(data, ensure_ascii=False, indent=2))


def add_common_opts(parser):
    parser.add_argument("--base-url", default=None, help="覆盖 GATEWAY_BASE_URL")
    parser.add_argument("--token", default=None, help="覆盖 GATEWAY_API_KEY（API Key 或 JWT）")
    parser.add_argument("--raw", action="store_true", help="输出原始 JSON（不缩进）")


def make_client(args):
    client = ApiClient(base_url=args.base_url, token=args.token)
    return client


def run(handler):
    """包装命令处理函数，统一异常处理。"""
    def wrapper(args):
        try:
            result = handler(args)
            if result is not None:
                if getattr(args, "raw", False):
                    print(json.dumps(result, ensure_ascii=False))
                else:
                    print_json(result)
        except GatewayError as e:
            sys.stderr.write(f"API 错误: {e}\n")
            if e.details:
                sys.stderr.write(f"详情: {json.dumps(e.details, ensure_ascii=False)}\n")
            elif e.raw and e.message in ("HTTP Error 403: Forbidden", "HTTP Error 404: Not Found"):
                sys.stderr.write(f"原始响应: {e.raw[:800]}\n")
            sys.exit(1)
    return wrapper


# ---------------------------------------------------------------------------
# teams 命令
# ---------------------------------------------------------------------------

def cmd_teams_create(args):
    client = make_client(args)
    body = {"name": args.name}
    if args.slug:
        body["slug"] = args.slug
    if args.settings:
        body["settings"] = parse_json_arg(args.settings, "settings")
    return client.post("/gateway/teams", body=body)


def cmd_teams_list(args):
    return make_client(args).get("/gateway/teams")


def cmd_teams_find(args):
    """按名称或 slug 子串过滤团队（客户端过滤，避免手写脚本）。"""
    teams = make_client(args).get("/gateway/teams")
    if not isinstance(teams, list):
        teams = teams.get("items", [])
    needle = args.name_contains.lower()
    matched = [
        t
        for t in teams
        if needle in (t.get("name") or "").lower() or needle in (t.get("slug") or "").lower()
    ]
    if args.kind:
        matched = [t for t in matched if t.get("kind") == args.kind]
    if args.json_fields:
        fields = [f.strip() for f in args.json_fields.split(",")]
        matched = [{k: t.get(k) for k in fields if k in t} for t in matched]
    return matched


def cmd_teams_update(args):
    client = make_client(args)
    body = {}
    if args.name:
        body["name"] = args.name
    if args.slug:
        body["slug"] = args.slug
    if args.settings:
        body["settings"] = parse_json_arg(args.settings, "settings")
    if args.is_active is not None:
        body["is_active"] = args.is_active
    return client.patch(f"/gateway/teams/{args.team_id}", body=body)


def cmd_teams_delete(args):
    make_client(args).delete(f"/gateway/teams/{args.team_id}")
    return {"deleted": True, "team_id": args.team_id}


def cmd_teams_members_list(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/members")


def cmd_teams_members_add(args):
    client = make_client(args)
    body = {"user_id": args.user_id, "role": args.role}
    return client.post(f"/gateway/teams/{args.team_id}/members", body=body)


# ---------------------------------------------------------------------------
# credentials 命令
# ---------------------------------------------------------------------------

def cmd_creds_create(args):
    client = make_client(args)
    body = {"provider": args.provider, "name": args.name, "api_key": args.api_key}
    if args.api_base:
        body["api_base"] = args.api_base
    if args.profile_id:
        body["profile_id"] = args.profile_id
    if args.scope:
        body["scope"] = args.scope
    if args.extra:
        body["extra"] = parse_json_arg(args.extra, "extra")
    return client.post(f"/gateway/teams/{args.team_id}/credentials", body=body)


def cmd_creds_create_personal(args):
    client = make_client(args)
    body = {"provider": args.provider, "name": args.name, "api_key": args.api_key}
    if args.api_base:
        body["api_base"] = args.api_base
    if args.profile_id:
        body["profile_id"] = args.profile_id
    if args.extra:
        body["extra"] = parse_json_arg(args.extra, "extra")
    return client.post("/gateway/my-credentials", body=body)


def cmd_creds_list(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/credentials")


def cmd_creds_summaries(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/credentials/summaries")


def cmd_creds_get(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/credentials/{args.credential_id}")


def cmd_creds_reveal(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/credentials/{args.credential_id}/reveal")


def cmd_creds_probe(args):
    return make_client(args).post(f"/gateway/teams/{args.team_id}/credentials/{args.credential_id}/probe")


def cmd_creds_probe_personal(args):
    return make_client(args).post(f"/gateway/my-credentials/{args.credential_id}/probe")


def cmd_creds_update(args):
    client = make_client(args)
    body = {}
    if args.name:
        body["name"] = args.name
    if args.api_key:
        body["api_key"] = args.api_key
    if args.api_base:
        body["api_base"] = args.api_base
    if args.is_active is not None:
        body["is_active"] = args.is_active
    if args.profile_id:
        body["profile_id"] = args.profile_id
    return client.patch(f"/gateway/teams/{args.team_id}/credentials/{args.credential_id}", body=body)


def cmd_creds_delete(args):
    make_client(args).delete(f"/gateway/teams/{args.team_id}/credentials/{args.credential_id}")
    return {"deleted": True, "credential_id": args.credential_id}


def cmd_creds_profiles(args):
    return make_client(args).get("/gateway/provider-profiles")


# ---------------------------------------------------------------------------
# models 命令
# ---------------------------------------------------------------------------

def cmd_models_batch_import(args):
    client = make_client(args)
    items = parse_json_arg(args.items, "items")
    body = {"provider": args.provider, "items": items}
    if args.capability:
        body["capability"] = args.capability
    if args.weight is not None:
        body["weight"] = args.weight
    if args.rpm_limit is not None:
        body["rpm_limit"] = args.rpm_limit
    if args.tpm_limit is not None:
        body["tpm_limit"] = args.tpm_limit
    if args.enabled is not None:
        body["enabled"] = args.enabled
    if args.tags:
        body["tags"] = parse_json_arg(args.tags, "tags")
    return client.post(f"/gateway/teams/{args.team_id}/credentials/{args.credential_id}/batch-import-models", body=body)


def cmd_models_create(args):
    client = make_client(args)
    body = {
        "name": args.name, "capability": args.capability,
        "real_model": args.real_model, "credential_id": args.credential_id,
        "provider": args.provider,
    }
    if args.weight is not None:
        body["weight"] = args.weight
    if args.tags:
        body["tags"] = parse_json_arg(args.tags, "tags")
    if args.display_name:
        body["display_name"] = args.display_name
    if args.upstream_call_shape:
        body["upstream_call_shape"] = args.upstream_call_shape
    if args.enabled is not None:
        body["enabled"] = args.enabled
    return client.post(f"/gateway/teams/{args.team_id}/models", body=body)


def cmd_models_list(args):
    client = make_client(args)
    params = {
        "page": args.page, "page_size": args.page_size, "q": args.q,
        "connectivity": args.connectivity, "sort": args.sort, "order": args.order,
        "provider": args.provider, "credential_id": args.credential_id,
        "type": args.type, "enabled": args.enabled, "registry_scope": args.registry_scope,
    }
    if args.all:
        # 自动翻页拉取全部（page_size 上限 200，用 100 减少请求数）
        params["page"] = 1
        params["page_size"] = 100
        all_items = []
        while True:
            data = client.get(f"/gateway/teams/{args.team_id}/models", params=params)
            all_items.extend(data.get("items", []))
            if not data.get("has_next"):
                break
            params["page"] += 1
        return {"items": all_items, "total": data.get("total", len(all_items)),
                "page": 1, "page_size": len(all_items),
                "has_next": False, "has_prev": False,
                "connectivity_summary": data.get("connectivity_summary")}
    return client.get(f"/gateway/teams/{args.team_id}/models", params=params)


def cmd_models_get(args):
    client = make_client(args)
    params = {"registry_scope": args.registry_scope} if args.registry_scope else None
    return client.get(f"/gateway/teams/{args.team_id}/models/{args.model_id}", params=params)


def cmd_models_update(args):
    client = make_client(args)
    body = {}
    if args.name:
        body["name"] = args.name
    if args.real_model:
        body["real_model"] = args.real_model
    if args.credential_id:
        body["credential_id"] = args.credential_id
    if args.capability:
        body["capability"] = args.capability
    if args.model_types:
        body["model_types"] = parse_json_arg(args.model_types, "model_types")
    if args.tags:
        body["tags"] = parse_json_arg(args.tags, "tags")
    if args.display_name:
        body["display_name"] = args.display_name
    if args.resync_capabilities:
        body["resync_capabilities"] = True
    if args.enabled is not None:
        body["enabled"] = args.enabled
    if args.upstream_call_shape:
        body["upstream_call_shape"] = args.upstream_call_shape
    return client.patch(f"/gateway/teams/{args.team_id}/models/{args.model_id}", body=body)


def cmd_models_test(args):
    return make_client(args).post(f"/gateway/teams/{args.team_id}/models/{args.model_id}/test")


def cmd_models_delete(args):
    make_client(args).delete(f"/gateway/teams/{args.team_id}/models/{args.model_id}")
    return {"deleted": True, "model_id": args.model_id}


def cmd_models_batch_delete(args):
    client = make_client(args)
    model_ids = parse_json_arg(args.model_ids, "model_ids")
    return client.post(f"/gateway/teams/{args.team_id}/models/batch-delete", body={"model_ids": model_ids})


def cmd_models_copy_to_team(args):
    client = make_client(args)
    body = {
        "model_ids": parse_json_arg(args.model_ids, "model_ids"),
        "destination_team_id": args.destination_team_id,
        "credential_plans": parse_json_arg(args.credential_plans, "credential_plans"),
    }
    return client.post("/gateway/models/copy-to-team", body=body)


def cmd_models_resync(args):
    client = make_client(args)
    model_ids = parse_json_arg(args.model_ids, "model_ids")
    return client.post(f"/gateway/teams/{args.team_id}/models/batch-resync-capabilities",
                       body={"model_ids": model_ids})


def cmd_models_presets(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/models/presets")


def cmd_models_callable(args):
    client = make_client(args)
    params = {"team_id": args.team_id} if args.team_id else None
    return client.get("/gateway/my-route-callable-models", params=params)


def cmd_models_my_list(args):
    return make_client(args).get("/gateway/my-models")


def cmd_models_my_test(args):
    return make_client(args).post(f"/gateway/my-models/{args.model_id}/test")


def cmd_models_my_delete(args):
    make_client(args).delete(f"/gateway/my-models/{args.model_id}")
    return {"deleted": True, "model_id": args.model_id}


# ---------------------------------------------------------------------------
# routes 命令
# ---------------------------------------------------------------------------

def cmd_routes_my_list(args):
    return make_client(args).get("/gateway/my-routes")


def cmd_routes_my_create(args):
    client = make_client(args)
    body = {
        "virtual_model": args.virtual_model,
        "primary_models": parse_json_arg(args.primary_models, "primary_models"),
    }
    if args.strategy:
        body["strategy"] = args.strategy
    if args.fallbacks_general:
        body["fallbacks_general"] = parse_json_arg(args.fallbacks_general, "fallbacks_general")
    if args.fallbacks_content_policy:
        body["fallbacks_content_policy"] = parse_json_arg(args.fallbacks_content_policy, "fallbacks_content_policy")
    if args.fallbacks_context_window:
        body["fallbacks_context_window"] = parse_json_arg(args.fallbacks_context_window, "fallbacks_context_window")
    if args.retry_policy:
        body["retry_policy"] = parse_json_arg(args.retry_policy, "retry_policy")
    return client.post("/gateway/my-routes", body=body)


def cmd_routes_my_update(args):
    client = make_client(args)
    body = {}
    if args.virtual_model:
        body["virtual_model"] = args.virtual_model
    if args.primary_models:
        body["primary_models"] = parse_json_arg(args.primary_models, "primary_models")
    if args.strategy:
        body["strategy"] = args.strategy
    if args.enabled is not None:
        body["enabled"] = args.enabled
    return client.patch(f"/gateway/my-routes/{args.route_id}", body=body)


def cmd_routes_my_delete(args):
    make_client(args).delete(f"/gateway/my-routes/{args.route_id}")
    return {"deleted": True, "route_id": args.route_id}


def cmd_routes_my_callable(args):
    client = make_client(args)
    params = {"team_id": args.team_id} if args.team_id else None
    return client.get("/gateway/my-route-callable-models", params=params)


def cmd_routes_team_list(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/routes")


def cmd_routes_team_create(args):
    client = make_client(args)
    body = {
        "virtual_model": args.virtual_model,
        "primary_models": parse_json_arg(args.primary_models, "primary_models"),
    }
    if args.strategy:
        body["strategy"] = args.strategy
    return client.post(f"/gateway/teams/{args.team_id}/routes", body=body)


def cmd_routes_team_delete(args):
    make_client(args).delete(f"/gateway/teams/{args.team_id}/routes/{args.route_id}")
    return {"deleted": True, "route_id": args.route_id}


def cmd_grants_list(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/keys/{args.key_id}/grants")


def cmd_grants_create(args):
    client = make_client(args)
    body = {"tenant_ids": parse_json_arg(args.tenant_ids, "tenant_ids")}
    return client.post(f"/gateway/teams/{args.team_id}/keys/{args.key_id}/grants", body=body)


def cmd_grants_grantable(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/keys/{args.key_id}/grants/grantable-teams")


def cmd_routes_route_grants_list(args):
    return make_client(args).get(f"/gateway/my-routes/{args.route_id}/grants")


def cmd_routes_route_grants_create(args):
    client = make_client(args)
    body = {"target_tenant_id": args.target_team_id}
    if args.exposed_alias:
        body["exposed_alias"] = args.exposed_alias
    return client.post(f"/gateway/my-routes/{args.route_id}/grants", body=body)


def cmd_routes_route_grants_delete(args):
    make_client(args).delete(f"/gateway/my-routes/{args.route_id}/grants/{args.target_team_id}")
    return {"revoked": True, "route_id": args.route_id, "target_team_id": args.target_team_id}


def cmd_routes_route_grants_grantable(args):
    return make_client(args).get(f"/gateway/my-routes/{args.route_id}/grantable-teams")


def cmd_routes_shared_routes_list(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/shared-routes")


def cmd_routes_route_grants_publish(args):
    """批量把个人路由发布到目标团队（跳过已授权项）。"""
    client = make_client(args)
    target_team_id = args.target_team_id
    routes = client.get("/gateway/my-routes")
    if not isinstance(routes, list):
        routes = routes.get("items", [])

    if args.all_routes:
        selected = routes
    elif args.route_ids:
        wanted = {rid.strip() for rid in args.route_ids.split(",") if rid.strip()}
        selected = [r for r in routes if r.get("id") in wanted]
        missing = wanted - {r.get("id") for r in selected}
        if missing:
            sys.stderr.write(f"警告：未找到路由 id: {', '.join(sorted(missing))}\n")
    else:
        sys.stderr.write("需要 --all-routes 或 --route-ids <id1,id2>\n")
        sys.exit(2)

    results = []
    for route in selected:
        rid = route["id"]
        grants = client.get(f"/gateway/my-routes/{rid}/grants")
        if not isinstance(grants, list):
            grants = grants.get("items", [])
        if any(g.get("tenant_id") == target_team_id for g in grants):
            results.append(
                {
                    "route_id": rid,
                    "virtual_model": route.get("virtual_model"),
                    "status": "already_granted",
                }
            )
            continue
        body = {"target_tenant_id": target_team_id}
        if args.exposed_alias:
            body["exposed_alias"] = args.exposed_alias
        grant = client.post(f"/gateway/my-routes/{rid}/grants", body=body)
        results.append(
            {
                "route_id": rid,
                "virtual_model": route.get("virtual_model"),
                "status": "created",
                "grant": grant,
            }
        )
    return results


# ---------------------------------------------------------------------------
# auth / logs / stats
# ---------------------------------------------------------------------------

def cmd_auth_whoami(args):
    return make_client(args).get("/auth/me")


def cmd_logs_list(args):
    client = make_client(args)
    params = {
        "page": args.page,
        "page_size": args.page_size,
        "usage_aggregation": args.usage_aggregation,
        "start": args.start,
        "end": args.end,
        "status": args.status,
        "capability": args.capability,
        "vkey_id": args.vkey_id,
        "credential_id": args.credential_id,
        "user_id": args.user_id,
        "model": args.model,
        "client_type": args.client_type,
    }
    return client.get(f"/gateway/teams/{args.team_id}/logs", params=params)


def cmd_logs_get(args):
    detail = make_client(args).get(f"/gateway/teams/{args.team_id}/logs/{args.log_id}")
    if args.attribution_only:
        snap = detail.get("route_snapshot") or {}
        return {
            "id": detail.get("id"),
            "created_at": detail.get("created_at"),
            "team_id": detail.get("team_id"),
            "user_id": detail.get("user_id"),
            "user_email_snapshot": detail.get("user_email_snapshot"),
            "vkey_id": detail.get("vkey_id"),
            "route_name": detail.get("route_name"),
            "status": detail.get("status"),
            "route_snapshot": snap,
            "delegated": bool(snap.get("delegated")),
            "resource_owner_user_id": snap.get("owner_user_id"),
        }
    return detail


def cmd_stats_summary(args):
    client = make_client(args)
    params = {
        "group_by": args.group_by,
        "usage_aggregation": args.usage_aggregation,
        "start": args.start,
        "end": args.end,
    }
    return client.get(f"/gateway/teams/{args.team_id}/dashboard/statistics", params=params)


# ---------------------------------------------------------------------------
# quotas 命令
# ---------------------------------------------------------------------------

def cmd_quotas_list(args):
    client = make_client(args)
    params = {
        "layer": args.layer, "user_id": args.user_id,
        "credential_id": args.credential_id, "model_name": args.model_name,
        "period": args.period, "include_usage": args.include_usage,
        "page": args.page, "page_size": args.page_size,
    }
    return client.get(f"/gateway/teams/{args.team_id}/quota-rules", params=params)


def _parse_reset_minutes(reset_at):
    """把 HH:MM 或 HHMM 或分钟数解析为分钟数。如 '17:00' -> 1020, '0900' -> 540, '600' -> 600。"""
    if reset_at is None:
        return None
    s = str(reset_at).strip()
    if s.isdigit():
        return int(s)
    if ":" in s:
        h, m = s.split(":", 1)
        return int(h) * 60 + int(m)
    raise ValueError(f"无法解析重置时间: {reset_at}（用 HH:MM 或分钟数，如 17:00 或 1020）")


def cmd_quotas_batch_upsert(args):
    """批量 upsert 配额规则。

    两种模式：
    1. 显式规则：--rules '[{...}, {...}]'（完整控制每条规则）
    2. 便捷模式：--credential-id + --limit-tokens/--limit-usd + (--models|--all-models)
       自动为指定凭据下的（全部或指定）模型生成规则，避免手写 N 条 JSON。
    """
    client = make_client(args)

    if args.rules:
        rules = parse_json_arg(args.rules, "rules")
        return client.put(f"/gateway/teams/{args.team_id}/quota-rules/batch", body={"rules": rules})

    # 便捷模式：必须有 credential_id 和至少一个限额字段
    if not args.credential_id:
        sys.stderr.write(
            "错误：便捷模式需要 --credential-id（或用 --rules 显式传规则）。\n"
            "便捷模式用法：--credential-id <cid> --limit-tokens 4800000 --all-models --reset-at 17:00\n"
        )
        sys.exit(2)
    if not args.limit_tokens and not args.limit_usd:
        sys.stderr.write("错误：便捷模式需要 --limit-tokens 或 --limit-usd。\n")
        sys.exit(2)

    # 确定 model_name 列表
    if args.models:
        model_names = [m.strip() for m in args.models.split(",") if m.strip()]
    elif args.all_models:
        # 从团队模型列表自动拉取该凭据下的全部模型
        data = client.get(f"/gateway/teams/{args.team_id}/models",
                          params={"credential_id": args.credential_id, "page_size": 200})
        model_names = [m["real_model"] for m in data.get("items", []) if m.get("real_model")]
        if not model_names:
            sys.stderr.write(f"错误：凭据 {args.credential_id} 下未找到任何模型。\n")
            sys.exit(1)
        sys.stderr.write(f"[info] 从凭据 {args.credential_id} 下拉取到 {len(model_names)} 个模型\n")
    else:
        sys.stderr.write("错误：便捷模式需要 --models <逗号分隔> 或 --all-models。\n")
        sys.exit(2)

    reset_minutes = _parse_reset_minutes(args.reset_at) if args.reset_at else None
    rules = []
    for mn in model_names:
        # label 用去掉 provider 前缀的简短名（quota_label max_length=40）
        short_name = mn.split("/", 1)[1] if "/" in mn else mn
        label = f"{short_name} 日限额"
        if len(label) > 40:
            label = label[:37] + "..."  # 截断到 40 字符内
        rule = {
            "layer": "upstream",
            "credential_id": args.credential_id,
            "model_name": mn,  # 完整 real_model（含 provider 前缀）
            "window_seconds": 86400,
            "reset_strategy": "calendar_daily_utc",
            "period_timezone": args.timezone or "Asia/Shanghai",
            "quota_label": label,
            "enabled": True,
        }
        if reset_minutes is not None:
            rule["period_reset_minutes"] = reset_minutes
        if args.limit_tokens:
            rule["limit_tokens"] = int(args.limit_tokens)
        if args.limit_usd:
            rule["limit_usd"] = args.limit_usd
        if args.soft_limit_usd:
            rule["soft_limit_usd"] = args.soft_limit_usd
        rules.append(rule)

    sys.stderr.write(f"[info] 准备 upsert {len(rules)} 条上游限额规则\n")
    return client.put(f"/gateway/teams/{args.team_id}/quota-rules/batch", body={"rules": rules})


def cmd_quotas_self_batch(args):
    client = make_client(args)
    rules = parse_json_arg(args.rules, "rules")
    return client.put(f"/gateway/teams/{args.team_id}/quota-rules/self-batch", body={"rules": rules})


def cmd_quotas_enablement(args):
    client = make_client(args)
    body = {
        "layer": args.layer, "budget_id": args.budget_id,
        "plan_id": args.plan_id, "quota_id": args.quota_id, "enabled": args.enabled,
    }
    return client.post(f"/gateway/teams/{args.team_id}/quota-rules/enablement", body=body)


def cmd_quotas_usage_adjustment(args):
    client = make_client(args)
    body = {
        "layer": args.layer, "budget_id": args.budget_id,
        "plan_id": args.plan_id, "quota_id": args.quota_id, "mode": args.mode,
    }
    if args.current_usd is not None:
        body["current_usd"] = args.current_usd
    if args.current_tokens is not None:
        body["current_tokens"] = args.current_tokens
    if args.current_requests is not None:
        body["current_requests"] = args.current_requests
    return client.post(f"/gateway/teams/{args.team_id}/quota-rules/usage-adjustments", body=body)


def cmd_quotas_delete(args):
    client = make_client(args)
    params = {"layer": args.layer, "quota_id": args.quota_id, "plan_id": args.plan_id}
    client.delete(f"/gateway/teams/{args.team_id}/quota-rules/plan", params=params)
    return {"deleted": True, "layer": args.layer, "quota_id": args.quota_id}


def cmd_budgets_list(args):
    client = make_client(args)
    params = {"target_kind": args.target_kind, "model_name": args.model_name}
    return client.get(f"/gateway/teams/{args.team_id}/budgets", params=params)


# ---------------------------------------------------------------------------
# vkeys 命令（Virtual Key 管理）
# ---------------------------------------------------------------------------

def _ensure_vkey(client, team_id, name):
    """智能获取 vkey 明文：同名存在则 reveal 复用，否则创建。

    返回 (vkey_id, plain_key, reused)。
    """
    data = client.get(f"/gateway/teams/{team_id}/keys")
    items = data if isinstance(data, list) else data.get("items", [])
    for v in items:
        if v.get("name") == name and v.get("is_active"):
            revealed = client.get(f"/gateway/teams/{team_id}/keys/{v['id']}/reveal")
            plain = revealed.get("plain_key") or revealed.get("key")
            return v["id"], plain, True
    created = client.post(f"/gateway/teams/{team_id}/keys", body={"name": name})
    return created["id"], created.get("plain_key"), False


def cmd_vkeys_list(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/keys")


def cmd_vkeys_create(args):
    client = make_client(args)
    body = {"name": args.name}
    if args.description:
        body["description"] = args.description
    if args.guardrail_enabled is not None:
        body["guardrail_enabled"] = args.guardrail_enabled
    return client.post(f"/gateway/teams/{args.team_id}/keys", body=body)


def cmd_vkeys_reveal(args):
    return make_client(args).get(f"/gateway/teams/{args.team_id}/keys/{args.key_id}/reveal")


def cmd_vkeys_ensure(args):
    """智能获取 vkey：同名复用 reveal，无则创建，返回明文。"""
    client = make_client(args)
    vkey_id, plain_key, reused = _ensure_vkey(client, args.team_id, args.name)
    if reused:
        sys.stderr.write(f"[info] 复用已有 vkey: id={vkey_id} name={args.name}\n")
    else:
        sys.stderr.write(f"[info] 创建新 vkey: id={vkey_id} name={args.name}\n")
    return {"id": vkey_id, "name": args.name, "plain_key": plain_key, "reused": reused}


def cmd_vkeys_delete(args):
    make_client(args).delete(f"/gateway/teams/{args.team_id}/keys/{args.key_id}")
    return {"deleted": True, "key_id": args.key_id}


# ---------------------------------------------------------------------------
# proxy 命令（通过网关代理调用模型，自动 ensure vkey）
# ---------------------------------------------------------------------------

def cmd_proxy_chat(args):
    """聊天补全：自动 ensure vkey 后调 /openai/v1/chat/completions。"""
    client = make_client(args)
    vkey_name = args.vkey_name or "gateway-proxy"
    vkey_id, plain_key, reused = _ensure_vkey(client, args.team_id, vkey_name)
    if reused:
        sys.stderr.write(f"[info] 复用 vkey {vkey_id} (name={vkey_name})\n")
    else:
        sys.stderr.write(f"[info] 创建 vkey {vkey_id} (name={vkey_name})\n")
    proxy = ApiClient(base_url=client.base_url, token=plain_key)
    body = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.message}],
    }
    if args.max_tokens is not None:
        body["max_tokens"] = args.max_tokens
    if args.temperature is not None:
        body["temperature"] = args.temperature
    return proxy.post("/openai/v1/chat/completions", body=body)


def cmd_proxy_image(args):
    """文生图：自动 ensure vkey 后调 /openai/v1/images/generations。"""
    client = make_client(args)
    vkey_name = args.vkey_name or "gateway-proxy"
    vkey_id, plain_key, reused = _ensure_vkey(client, args.team_id, vkey_name)
    if reused:
        sys.stderr.write(f"[info] 复用 vkey {vkey_id} (name={vkey_name})\n")
    else:
        sys.stderr.write(f"[info] 创建 vkey {vkey_id} (name={vkey_name})\n")
    proxy = ApiClient(base_url=client.base_url, token=plain_key)
    body = {"model": args.model, "prompt": args.prompt, "n": args.n or 1}
    if args.size:
        body["size"] = args.size
    return proxy.post("/openai/v1/images/generations", body=body)


def cmd_proxy_models(args):
    """列出代理端可见模型（含共享进团队的路由别名）。"""
    client = make_client(args)
    vkey_name = args.vkey_name or "gateway-proxy"
    _vkey_id, plain_key, reused = _ensure_vkey(client, args.team_id, vkey_name)
    if reused:
        sys.stderr.write(f"[info] 复用 vkey (name={vkey_name})\n")
    proxy = ApiClient(base_url=client.base_url, token=plain_key)
    data = proxy.get("/openai/v1/models")
    items = data.get("data", []) if isinstance(data, dict) else []
    if args.filter:
        needle = args.filter.lower()
        items = [m for m in items if needle in (m.get("id") or "").lower()]
    if args.ids_only:
        return [m.get("id") for m in items]
    if args.filter or args.ids_only:
        return {"object": "list", "data": items}
    return data


# ---------------------------------------------------------------------------
# 参数解析构建
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="gateway_client",
        description="AI Gateway Ops CLI - 管理团队/凭据/模型/路由/配额",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_opts(parser)
    sub = parser.add_subparsers(dest="category", required=True, metavar="<category>")

    _build_teams(sub)
    _build_auth(sub)
    _build_credentials(sub)
    _build_models(sub)
    _build_routes(sub)
    _build_quotas(sub)
    _build_vkeys(sub)
    _build_logs(sub)
    _build_stats(sub)
    _build_proxy(sub)
    return parser


def _build_teams(sub):
    p = sub.add_parser("teams", help="团队管理")
    sp = p.add_subparsers(dest="command", required=True, metavar="<command>")

    c = sp.add_parser("create", help="创建团队")
    c.add_argument("--name", required=True, help="团队名称")
    c.add_argument("--slug", help="URL slug（缺省自动生成）")
    c.add_argument("--settings", help="团队设置 JSON")
    c.set_defaults(func=run(cmd_teams_create))

    c = sp.add_parser("list", help="列出可见团队")
    c.set_defaults(func=run(cmd_teams_list))

    c = sp.add_parser("find", help="按名称/slug 子串查找团队（输出 id/name/slug）")
    c.add_argument("--name-contains", required=True, help="名称或 slug 子串，如 研发API")
    c.add_argument("--kind", choices=["personal", "shared", "system"], help="按团队类型过滤")
    c.add_argument(
        "--json-fields",
        default="id,name,slug,kind,team_role",
        help="输出字段（逗号分隔）",
    )
    c.set_defaults(func=run(cmd_teams_find))

    c = sp.add_parser("update", help="更新团队")
    c.add_argument("--team-id", required=True)
    c.add_argument("--name")
    c.add_argument("--slug")
    c.add_argument("--settings", help="设置 JSON")
    c.add_argument("--is-active", type=lambda x: x.lower() == "true", default=None)
    c.set_defaults(func=run(cmd_teams_update))

    c = sp.add_parser("delete", help="删除团队")
    c.add_argument("--team-id", required=True)
    c.set_defaults(func=run(cmd_teams_delete))

    m = sp.add_parser("members", help="成员管理")
    msp = m.add_subparsers(dest="mcommand", required=True, metavar="<command>")
    c = msp.add_parser("list", help="列出成员")
    c.add_argument("--team-id", required=True)
    c.set_defaults(func=run(cmd_teams_members_list))
    c = msp.add_parser("add", help="添加成员")
    c.add_argument("--team-id", required=True)
    c.add_argument("--user-id", required=True)
    c.add_argument("--role", default="member", help="owner/admin/member")
    c.set_defaults(func=run(cmd_teams_members_add))


def _build_credentials(sub):
    p = sub.add_parser("credentials", help="凭据管理")
    sp = p.add_subparsers(dest="command", required=True, metavar="<command>")

    c = sp.add_parser("create", help="创建团队/系统凭据")
    c.add_argument("--team-id", required=True)
    c.add_argument("--provider", required=True, help="提供商（openai/anthropic/...）")
    c.add_argument("--name", required=True, help="展示名")
    c.add_argument("--api-key", required=True, help="明文 API Key")
    c.add_argument("--api-base", help="OpenAI-compat base URL")
    c.add_argument("--profile-id", help="上游方案 ID")
    c.add_argument("--scope", choices=["team", "system"], default="team", help="写入目标（system 需平台 admin）")
    c.add_argument("--extra", help="扩展字段 JSON")
    c.set_defaults(func=run(cmd_creds_create))

    c = sp.add_parser("create-personal", help="创建个人 BYOK 凭据")
    c.add_argument("--provider", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--api-key", required=True)
    c.add_argument("--api-base")
    c.add_argument("--profile-id")
    c.add_argument("--extra", help="扩展字段 JSON")
    c.set_defaults(func=run(cmd_creds_create_personal))

    c = sp.add_parser("list", help="列出团队凭据")
    c.add_argument("--team-id", required=True)
    c.set_defaults(func=run(cmd_creds_list))

    c = sp.add_parser("summaries", help="凭据摘要列表")
    c.add_argument("--team-id", required=True)
    c.set_defaults(func=run(cmd_creds_summaries))

    c = sp.add_parser("get", help="凭据详情")
    c.add_argument("--team-id", required=True)
    c.add_argument("--credential-id", required=True)
    c.set_defaults(func=run(cmd_creds_get))

    c = sp.add_parser("reveal", help="解密返回明文 API Key")
    c.add_argument("--team-id", required=True)
    c.add_argument("--credential-id", required=True)
    c.set_defaults(func=run(cmd_creds_reveal))

    c = sp.add_parser("probe", help="探测凭据上游支持的模型")
    c.add_argument("--team-id", required=True)
    c.add_argument("--credential-id", required=True)
    c.set_defaults(func=run(cmd_creds_probe))

    c = sp.add_parser("probe-personal", help="探测个人凭据上游模型")
    c.add_argument("--credential-id", required=True)
    c.set_defaults(func=run(cmd_creds_probe_personal))

    c = sp.add_parser("update", help="更新凭据")
    c.add_argument("--team-id", required=True)
    c.add_argument("--credential-id", required=True)
    c.add_argument("--name")
    c.add_argument("--api-key")
    c.add_argument("--api-base")
    c.add_argument("--profile-id")
    c.add_argument("--is-active", type=lambda x: x.lower() == "true", default=None)
    c.set_defaults(func=run(cmd_creds_update))

    c = sp.add_parser("delete", help="删除凭据")
    c.add_argument("--team-id", required=True)
    c.add_argument("--credential-id", required=True)
    c.set_defaults(func=run(cmd_creds_delete))

    c = sp.add_parser("profiles", help="查看上游 Profile SSOT")
    c.set_defaults(func=run(cmd_creds_profiles))


def _build_models(sub):
    p = sub.add_parser("models", help="模型管理")
    sp = p.add_subparsers(dest="command", required=True, metavar="<command>")

    c = sp.add_parser("batch-import", help="批量导入上游模型到团队")
    c.add_argument("--team-id", required=True)
    c.add_argument("--credential-id", required=True)
    c.add_argument("--provider", required=True)
    c.add_argument("--items", required=True, help='JSON 数组，如 [{"upstream_model_id":"gpt-4o"}]')
    c.add_argument("--capability", default="chat", help="主调用面")
    c.add_argument("--weight", type=int)
    c.add_argument("--rpm-limit", type=int)
    c.add_argument("--tpm-limit", type=int)
    c.add_argument("--enabled", type=lambda x: x.lower() == "true", default=None)
    c.add_argument("--tags", help="标签 JSON")
    c.set_defaults(func=run(cmd_models_batch_import))

    c = sp.add_parser("create", help="手动注册单个团队模型")
    c.add_argument("--team-id", required=True)
    c.add_argument("--name", required=True, help="虚拟模型别名")
    c.add_argument("--capability", required=True, help="主调用面")
    c.add_argument("--real-model", required=True, help="真实模型 ID")
    c.add_argument("--credential-id", required=True)
    c.add_argument("--provider", required=True)
    c.add_argument("--weight", type=int)
    c.add_argument("--tags", help="标签 JSON（能力位）")
    c.add_argument("--display-name")
    c.add_argument("--upstream-call-shape", choices=["openai_compat", "anthropic_native"])
    c.add_argument("--enabled", type=lambda x: x.lower() == "true", default=None)
    c.set_defaults(func=run(cmd_models_create))

    c = sp.add_parser("list", help="列出团队模型（默认 page_size=100；--all 自动翻页拉全部）")
    c.add_argument("--team-id", required=True)
    c.add_argument("--page", type=int)
    c.add_argument("--page-size", type=int, default=100, help="默认 100（API 默认 20 易分页不全）")
    c.add_argument("--all", action="store_true", help="自动翻页拉取全部模型（忽略 --page/--page-size）")
    c.add_argument("--q", help="模糊搜索")
    c.add_argument("--connectivity", choices=["all", "success", "failed", "unknown"])
    c.add_argument("--sort", choices=["name", "created_at", "provider", "last_tested_at"])
    c.add_argument("--order", choices=["asc", "desc"])
    c.add_argument("--provider")
    c.add_argument("--credential-id")
    c.add_argument("--type", help="能力筛选")
    c.add_argument("--enabled", type=lambda x: x.lower() == "true", default=None)
    c.add_argument("--registry-scope", choices=["team", "system", "callable", "requestable", "system_requestable"])
    c.set_defaults(func=run(cmd_models_list))

    c = sp.add_parser("get", help="模型详情")
    c.add_argument("--team-id", required=True)
    c.add_argument("--model-id", required=True)
    c.add_argument("--registry-scope", choices=["team", "system", "callable", "requestable", "system_requestable"])
    c.set_defaults(func=run(cmd_models_get))

    c = sp.add_parser("update", help="修改模型（含能力位）")
    c.add_argument("--team-id", required=True)
    c.add_argument("--model-id", required=True)
    c.add_argument("--name")
    c.add_argument("--real-model")
    c.add_argument("--credential-id")
    c.add_argument("--capability")
    c.add_argument("--model-types", help='JSON 数组，如 ["text","image"]')
    c.add_argument("--tags", help='标签 JSON，如 {"supports_vision":true}')
    c.add_argument("--display-name")
    c.add_argument("--resync-capabilities", action="store_true", help="从 LiteLLM 重算能力")
    c.add_argument("--enabled", type=lambda x: x.lower() == "true", default=None)
    c.add_argument("--upstream-call-shape", choices=["openai_compat", "anthropic_native"])
    c.set_defaults(func=run(cmd_models_update))

    c = sp.add_parser("test", help="测试模型连通性")
    c.add_argument("--team-id", required=True)
    c.add_argument("--model-id", required=True)
    c.set_defaults(func=run(cmd_models_test))

    c = sp.add_parser("delete", help="删除单个模型")
    c.add_argument("--team-id", required=True)
    c.add_argument("--model-id", required=True)
    c.set_defaults(func=run(cmd_models_delete))

    c = sp.add_parser("batch-delete", help="批量删除模型")
    c.add_argument("--team-id", required=True)
    c.add_argument("--model-ids", required=True, help='JSON 数组，如 ["uuid1","uuid2"]')
    c.set_defaults(func=run(cmd_models_batch_delete))

    c = sp.add_parser("copy-to-team", help="跨团队复制模型")
    c.add_argument("--model-ids", required=True, help="JSON 数组")
    c.add_argument("--destination-team-id", required=True)
    c.add_argument("--credential-plans", required=True, help='JSON 数组，如 [{"source_credential_id":"...","mode":"existing","destination_credential_id":"..."}]')
    c.set_defaults(func=run(cmd_models_copy_to_team))

    c = sp.add_parser("resync", help="批量重算模型能力")
    c.add_argument("--team-id", required=True)
    c.add_argument("--model-ids", required=True, help="JSON 数组")
    c.set_defaults(func=run(cmd_models_resync))

    c = sp.add_parser("presets", help="模型预设目录")
    c.add_argument("--team-id", required=True)
    c.set_defaults(func=run(cmd_models_presets))

    c = sp.add_parser("callable-models", help="列出个人可调用模型（跨团队，用于路由引用）")
    c.add_argument("--team-id", help="按归属团队过滤")
    c.set_defaults(func=run(cmd_models_callable))

    c = sp.add_parser("my-list", help="列出个人模型")
    c.set_defaults(func=run(cmd_models_my_list))

    c = sp.add_parser("my-test", help="测试个人模型")
    c.add_argument("--model-id", required=True)
    c.set_defaults(func=run(cmd_models_my_test))

    c = sp.add_parser("my-delete", help="删除个人模型")
    c.add_argument("--model-id", required=True)
    c.set_defaults(func=run(cmd_models_my_delete))


def _build_routes(sub):
    p = sub.add_parser("routes", help="路由管理（个人工作区与团队）")
    sp = p.add_subparsers(dest="command", required=True, metavar="<command>")

    c = sp.add_parser("my-list", help="列出个人路由")
    c.set_defaults(func=run(cmd_routes_my_list))

    c = sp.add_parser("my-create", help="创建个人路由（可跨团队引用）")
    c.add_argument("--virtual-model", required=True, help="虚拟模型名")
    c.add_argument("--primary-models", required=True, help='JSON 数组，如 ["rd-team/gpt-4o","alias"]')
    c.add_argument("--strategy", help="调度策略")
    c.add_argument("--fallbacks-general", help="JSON 数组")
    c.add_argument("--fallbacks-content-policy", help="JSON 数组")
    c.add_argument("--fallbacks-context-window", help="JSON 数组")
    c.add_argument("--retry-policy", help="JSON 对象")
    c.set_defaults(func=run(cmd_routes_my_create))

    c = sp.add_parser("my-update", help="更新个人路由")
    c.add_argument("--route-id", required=True)
    c.add_argument("--virtual-model")
    c.add_argument("--primary-models", help="JSON 数组")
    c.add_argument("--strategy")
    c.add_argument("--enabled", type=lambda x: x.lower() == "true", default=None)
    c.set_defaults(func=run(cmd_routes_my_update))

    c = sp.add_parser("my-delete", help="删除个人路由")
    c.add_argument("--route-id", required=True)
    c.set_defaults(func=run(cmd_routes_my_delete))

    c = sp.add_parser("my-callable-models", help="列出可引用模型（含 route_ref）")
    c.add_argument("--team-id", help="按归属团队过滤")
    c.set_defaults(func=run(cmd_routes_my_callable))

    c = sp.add_parser("team-list", help="列出团队路由")
    c.add_argument("--team-id", required=True)
    c.set_defaults(func=run(cmd_routes_team_list))

    c = sp.add_parser("team-create", help="创建团队路由")
    c.add_argument("--team-id", required=True)
    c.add_argument("--virtual-model", required=True)
    c.add_argument("--primary-models", required=True, help="JSON 数组")
    c.add_argument("--strategy")
    c.set_defaults(func=run(cmd_routes_team_create))

    c = sp.add_parser("team-delete", help="删除团队路由")
    c.add_argument("--team-id", required=True)
    c.add_argument("--route-id", required=True)
    c.set_defaults(func=run(cmd_routes_team_delete))

    # vkey grants（跨团队授权）
    g = sp.add_parser("grants-list", help="列出 vkey 跨团队授权")
    g.add_argument("--team-id", required=True)
    g.add_argument("--key-id", required=True)
    g.set_defaults(func=run(cmd_grants_list))

    g = sp.add_parser("grants-create", help="授权 vkey 到其他团队")
    g.add_argument("--team-id", required=True)
    g.add_argument("--key-id", required=True)
    g.add_argument("--tenant-ids", required=True, help='JSON 数组，如 ["team-uuid-1"]')
    g.set_defaults(func=run(cmd_grants_create))

    g = sp.add_parser("grants-grantable", help="列出可授权团队")
    g.add_argument("--team-id", required=True)
    g.add_argument("--key-id", required=True)
    g.set_defaults(func=run(cmd_grants_grantable))

    # Route Team Grants（路由跨团队共享，委派模式）
    rg = sp.add_parser("route-grants-list", help="列出某条个人路由的共享授权")
    rg.add_argument("--route-id", required=True)
    rg.set_defaults(func=run(cmd_routes_route_grants_list))

    rg = sp.add_parser("route-grants-create", help="发布个人路由到团队")
    rg.add_argument("--route-id", required=True)
    rg.add_argument("--target-team-id", required=True)
    rg.add_argument("--exposed-alias", help="消费团队内调用名（默认=virtual_model）")
    rg.set_defaults(func=run(cmd_routes_route_grants_create))

    rg = sp.add_parser("route-grants-delete", help="撤销路由共享")
    rg.add_argument("--route-id", required=True)
    rg.add_argument("--target-team-id", required=True)
    rg.set_defaults(func=run(cmd_routes_route_grants_delete))

    rg = sp.add_parser("route-grants-grantable", help="列出可共享目标团队")
    rg.add_argument("--route-id", required=True)
    rg.set_defaults(func=run(cmd_routes_route_grants_grantable))

    rg = sp.add_parser("shared-routes-list", help="列出共享进某团队的路由")
    rg.add_argument("--team-id", required=True)
    rg.set_defaults(func=run(cmd_routes_shared_routes_list))

    rg = sp.add_parser("route-grants-publish", help="批量发布个人路由到团队（跳过已授权）")
    rg.add_argument("--target-team-id", required=True)
    rg.add_argument("--all-routes", action="store_true", help="发布全部个人路由")
    rg.add_argument("--route-ids", help="逗号分隔的 route_id 列表")
    rg.add_argument("--exposed-alias", help="统一暴露别名（通常省略，用各路由 virtual_model）")
    rg.set_defaults(func=run(cmd_routes_route_grants_publish))


def _build_quotas(sub):
    p = sub.add_parser("quotas", help="配额与限额管理")
    sp = p.add_subparsers(dest="command", required=True, metavar="<command>")

    c = sp.add_parser("list", help="查看配额规则（layer=upstream 查上游限额）")
    c.add_argument("--team-id", required=True)
    c.add_argument("--layer", choices=["platform", "upstream", "downstream"])
    c.add_argument("--user-id")
    c.add_argument("--credential-id", help="按凭据过滤（上游限额常用）")
    c.add_argument("--model-name")
    c.add_argument("--period", choices=["daily", "monthly", "total"])
    c.add_argument("--include-usage", type=lambda x: x.lower() == "true", default=None)
    c.add_argument("--page", type=int)
    c.add_argument("--page-size", type=int)
    c.set_defaults(func=run(cmd_quotas_list))

    c = sp.add_parser(
        "batch-upsert",
        help="批量 upsert 配额规则（含上游限额）。支持显式 --rules 或便捷模式",
        description=(
            "批量 upsert 配额规则。两种模式：\n"
            "  1) 显式：--rules '[{...}]'\n"
            "  2) 便捷：--credential-id CID --limit-tokens 4800000 --all-models --reset-at 17:00\n"
            "     自动从团队模型列表拉取该凭据下的全部模型，为每个生成一条规则。\n"
            "\n"
            "重要：model_name 必须用完整 real_model（含 provider 前缀，如 volcengine/gpt-4o），\n"
            "     否则生图/生视频等模型会报'未注册在该凭据下'。便捷模式自动用 real_model。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    c.add_argument("--team-id", required=True)
    c.add_argument("--rules", help='显式规则 JSON 数组，如 [{"layer":"upstream","credential_id":"...","model_name":"volcengine/gpt-4o","limit_tokens":4800000,"window_seconds":86400,"reset_strategy":"calendar_daily_utc","period_timezone":"Asia/Shanghai","period_reset_minutes":1020,"enabled":true}]')
    # 便捷模式参数
    c.add_argument("--credential-id", help="便捷模式：凭据 ID（自动拉取该凭据下模型）")
    c.add_argument("--limit-tokens", type=int, help="便捷模式：每日 token 限额（如 4800000）")
    c.add_argument("--limit-usd", help="便捷模式：每日金额限额（如 50.00）")
    c.add_argument("--soft-limit-usd", help="便捷模式：软限额金额")
    c.add_argument("--reset-at", help="便捷模式：每日重置时刻，HH:MM 或分钟数（如 17:00 或 1020）；不传则用服务端默认 0:00 UTC")
    c.add_argument("--timezone", default="Asia/Shanghai", help="便捷模式：时区，默认 Asia/Shanghai")
    c.add_argument("--models", help="便捷模式：逗号分隔的 model_name 列表（完整 real_model），不传则需 --all-models")
    c.add_argument("--all-models", action="store_true", help="便捷模式：自动拉取该凭据下全部模型")
    c.set_defaults(func=run(cmd_quotas_batch_upsert))

    c = sp.add_parser("self-batch", help="成员自助 upsert（仅本人凭据）")
    c.add_argument("--team-id", required=True)
    c.add_argument("--rules", required=True, help="JSON 数组")
    c.set_defaults(func=run(cmd_quotas_self_batch))

    c = sp.add_parser("enablement", help="启停单条配额")
    c.add_argument("--team-id", required=True)
    c.add_argument("--layer", required=True, choices=["platform", "upstream", "downstream"])
    c.add_argument("--budget-id")
    c.add_argument("--plan-id")
    c.add_argument("--quota-id")
    c.add_argument("--enabled", type=lambda x: x.lower() == "true", required=True)
    c.set_defaults(func=run(cmd_quotas_enablement))

    c = sp.add_parser("usage-adjustment", help="手工调整用量/清零窗口")
    c.add_argument("--team-id", required=True)
    c.add_argument("--layer", required=True, choices=["platform", "upstream", "downstream"])
    c.add_argument("--budget-id")
    c.add_argument("--plan-id")
    c.add_argument("--quota-id")
    c.add_argument("--mode", required=True, choices=["set", "reset_window"])
    c.add_argument("--current-usd")
    c.add_argument("--current-tokens", type=int)
    c.add_argument("--current-requests", type=int)
    c.set_defaults(func=run(cmd_quotas_usage_adjustment))

    c = sp.add_parser("delete", help="删除上游/下游配额")
    c.add_argument("--team-id", required=True)
    c.add_argument("--layer", required=True, choices=["upstream", "downstream"])
    c.add_argument("--quota-id", required=True)
    c.add_argument("--plan-id", required=True)
    c.set_defaults(func=run(cmd_quotas_delete))

    c = sp.add_parser("budgets-list", help="列出平台预算（旧式）")
    c.add_argument("--team-id", required=True)
    c.add_argument("--target-kind", choices=["system", "tenant", "key", "user"])
    c.add_argument("--model-name")
    c.set_defaults(func=run(cmd_budgets_list))


def _build_vkeys(sub):
    p = sub.add_parser("vkeys", help="Virtual Key 管理（代理调用凭据）")
    sp = p.add_subparsers(dest="command", required=True, metavar="<command>")

    c = sp.add_parser("list", help="列出团队 vkey")
    c.add_argument("--team-id", required=True)
    c.set_defaults(func=run(cmd_vkeys_list))

    c = sp.add_parser("create", help="创建 vkey")
    c.add_argument("--team-id", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--description")
    c.add_argument("--guardrail-enabled", type=lambda x: x.lower() == "true", default=None)
    c.set_defaults(func=run(cmd_vkeys_create))

    c = sp.add_parser("reveal", help="解密 vkey 明文")
    c.add_argument("--team-id", required=True)
    c.add_argument("--key-id", required=True)
    c.set_defaults(func=run(cmd_vkeys_reveal))

    c = sp.add_parser("ensure", help="智能获取 vkey（同名复用 reveal，无则创建），返回明文")
    c.add_argument("--team-id", required=True)
    c.add_argument("--name", required=True, help="vkey 名称（同名复用）")
    c.set_defaults(func=run(cmd_vkeys_ensure))

    c = sp.add_parser("delete", help="删除 vkey")
    c.add_argument("--team-id", required=True)
    c.add_argument("--key-id", required=True)
    c.set_defaults(func=run(cmd_vkeys_delete))


def _build_proxy(sub):
    p = sub.add_parser("proxy", help="通过网关代理调用模型（自动 ensure vkey）")
    sp = p.add_subparsers(dest="command", required=True, metavar="<command>")

    c = sp.add_parser("chat", help="聊天补全（自动获取/复用 vkey）")
    c.add_argument("--team-id", required=True)
    c.add_argument("--model", required=True, help="模型名或路由名")
    c.add_argument("--message", required=True, help="用户消息")
    c.add_argument("--vkey-name", default="gateway-proxy", help="vkey 名称（同名复用，默认 gateway-proxy）")
    c.add_argument("--max-tokens", type=int)
    c.add_argument("--temperature", type=float)
    c.set_defaults(func=run(cmd_proxy_chat))

    c = sp.add_parser("image", help="文生图（自动获取/复用 vkey）")
    c.add_argument("--team-id", required=True)
    c.add_argument("--model", required=True, help="生图模型名")
    c.add_argument("--prompt", required=True, help="生图提示词")
    c.add_argument("--n", type=int, default=1)
    c.add_argument("--size", help="图片尺寸，如 512x512")
    c.add_argument("--vkey-name", default="gateway-proxy", help="vkey 名称（同名复用）")
    c.set_defaults(func=run(cmd_proxy_image))

    c = sp.add_parser("models", help="列出代理端可见模型（含共享路由别名）")
    c.add_argument("--team-id", required=True)
    c.add_argument("--vkey-name", default="gateway-proxy")
    c.add_argument("--filter", help="按模型 id 子串过滤，如 volcano")
    c.add_argument("--ids-only", action="store_true", help="仅输出模型 id 列表")
    c.set_defaults(func=run(cmd_proxy_models))


def _build_auth(sub):
    p = sub.add_parser("auth", help="当前认证身份")
    sp = p.add_subparsers(dest="command", required=True, metavar="<command>")
    c = sp.add_parser("whoami", help="当前 API Key / JWT 对应用户")
    c.set_defaults(func=run(cmd_auth_whoami))


def _build_logs(sub):
    p = sub.add_parser("logs", help="请求日志（管理面）")
    sp = p.add_subparsers(dest="command", required=True, metavar="<command>")

    c = sp.add_parser("list", help="列出团队请求日志")
    c.add_argument("--team-id", required=True)
    c.add_argument("--page", type=int, default=1)
    c.add_argument("--page-size", type=int, default=20)
    c.add_argument(
        "--usage-aggregation",
        default="workspace",
        choices=["workspace", "user", "platform"],
        help="workspace=团队切片；user=当前用户跨团队",
    )
    c.add_argument("--start", help="ISO 起始时间")
    c.add_argument("--end", help="ISO 结束时间")
    c.add_argument("--status", help="success / failed / budget_exceeded 等")
    c.add_argument("--capability")
    c.add_argument("--vkey-id")
    c.add_argument("--credential-id")
    c.add_argument("--user-id")
    c.add_argument("--model", help="route_name 过滤")
    c.add_argument("--client-type")
    c.set_defaults(func=run(cmd_logs_list))

    c = sp.add_parser("get", help="单条日志详情")
    c.add_argument("--team-id", required=True)
    c.add_argument("--log-id", required=True)
    c.add_argument(
        "--attribution-only",
        action="store_true",
        help="仅输出 team/user/route_snapshot 归因字段",
    )
    c.set_defaults(func=run(cmd_logs_get))


def _build_stats(sub):
    p = sub.add_parser("stats", help="用量统计（管理面大盘）")
    sp = p.add_subparsers(dest="command", required=True, metavar="<command>")

    c = sp.add_parser("summary", help="按维度聚合用量")
    c.add_argument("--team-id", required=True)
    c.add_argument(
        "--group-by",
        default="user",
        choices=["user", "team", "credential", "model", "vkey", "provider", "resource_owner"],
    )
    c.add_argument("--usage-aggregation", default="workspace", choices=["workspace", "user", "platform"])
    c.add_argument("--start", help="ISO 起始时间")
    c.add_argument("--end", help="ISO 结束时间")
    c.set_defaults(func=run(cmd_stats_summary))


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(2)
    args.func(args)


if __name__ == "__main__":
    main()
