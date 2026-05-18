"""Gateway management routers (子 router 模块；由 ``management_router`` 聚合)。

按 ``presentation/management_router.py`` 历史 section 注释拆分；每个子模块导出
``router = APIRouter()``（不带 prefix；由聚合入口统一加 ``/api/v1/gateway`` + tags）。
"""
