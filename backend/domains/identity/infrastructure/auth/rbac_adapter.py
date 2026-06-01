"""
RBAC Infrastructure Adapter - RBAC 基础设施适配器

保留模块占位；当前项目路由统一使用 ``domains.identity.presentation.deps``
中的依赖注入（``require_role`` / ``AdminUser`` 等），本模块暂不额外提供
FastAPI 专用装饰器或中间件。
"""

# 项目中实际使用 ``deps.require_role`` 与团队角色依赖进行权限控制，
# 若后续需要更细粒度的基于 Permission 枚举的装饰器，可在此补充。
