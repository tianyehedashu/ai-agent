"""仅供 ``ALEMBIC_SQL_GEN_MOCK=1`` 时导出运维 SQL，不影响正常 ``alembic upgrade``。"""

from __future__ import annotations

import os


class _OfflineSqlGenMockResult:
    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list[object]:
        return []

    def scalar(self) -> None:
        return None

    def mappings(self):
        return self

    def __iter__(self):
        return iter(())


class _OfflineSqlGenMockInspector:
    def get_columns(self, _table_name: str, schema: str | None = None) -> list[dict[str, object]]:
        return []

    def get_indexes(self, _table_name: str, schema: str | None = None) -> list[dict[str, object]]:
        return []

    def get_unique_constraints(
        self, _table_name: str, schema: str | None = None
    ) -> list[dict[str, object]]:
        return []

    def get_table_names(self, schema: str | None = None) -> list[str]:
        return []

    def get_foreign_keys(
        self, table_name: str, schema: str | None = None
    ) -> list[dict[str, object]]:
        if table_name == "api_keys":
            return [
                {
                    "name": "api_keys_user_id_fkey",
                    "constrained_columns": ["user_id"],
                }
            ]
        if table_name == "api_key_usage_logs":
            return [
                {
                    "name": "api_key_usage_logs_api_key_id_fkey",
                    "constrained_columns": ["api_key_id"],
                }
            ]
        return []


class _SqlGenBindProxy:
    def __init__(self, inner: object | None) -> None:
        self._inner = inner

    def execute(self, statement, *multiparams, **params):
        sql_text = str(getattr(statement, "text", statement))
        normalized = sql_text.strip().upper()
        if "INFORMATION_SCHEMA" in normalized or normalized.startswith("SELECT"):
            return _OfflineSqlGenMockResult()
        if self._inner is None:
            return _OfflineSqlGenMockResult()
        return self._inner.execute(statement, *multiparams, **params)

    def __getattr__(self, name: str):
        if self._inner is None:
            msg = f"offline bind has no attribute {name!r}"
            raise AttributeError(msg)
        return getattr(self._inner, name)


def install_offline_sql_gen_mock() -> None:
    if os.environ.get("ALEMBIC_SQL_GEN_MOCK") != "1":
        return
    from alembic.ddl.impl import DefaultImpl
    from alembic.operations import Operations
    from sqlalchemy import inspection as sa_inspection
    from sqlalchemy.engine.base import Connection

    if getattr(DefaultImpl.execute, "_sql_gen_mock", False):
        return

    original_impl_execute = DefaultImpl.execute

    def impl_execute(self, sql, *multiparams, **params):
        sql_text = str(sql)
        normalized = sql_text.strip().upper()
        if "INFORMATION_SCHEMA" in normalized or normalized.startswith("SELECT"):
            return _OfflineSqlGenMockResult()
        return original_impl_execute(self, sql, *multiparams, **params)

    impl_execute._sql_gen_mock = True  # type: ignore[attr-defined]
    DefaultImpl.execute = impl_execute

    original_conn_execute = Connection.execute

    def conn_execute(self, statement, *multiparams, **params):
        sql_text = str(getattr(statement, "text", statement))
        normalized = sql_text.strip().upper()
        if "INFORMATION_SCHEMA" in normalized or normalized.startswith("SELECT"):
            return _OfflineSqlGenMockResult()
        return original_conn_execute(self, statement, *multiparams, **params)

    conn_execute._sql_gen_mock = True  # type: ignore[attr-defined]
    Connection.execute = conn_execute

    original_get_bind = Operations.get_bind

    def get_bind(self):
        return _SqlGenBindProxy(original_get_bind(self))

    get_bind._sql_gen_mock = True  # type: ignore[attr-defined]
    Operations.get_bind = get_bind

    if not getattr(sa_inspection, "_sql_gen_bind_registered", False):

        @sa_inspection._inspects(_SqlGenBindProxy)
        def _inspect_sql_gen_bind(bind: _SqlGenBindProxy) -> _OfflineSqlGenMockInspector:
            return _OfflineSqlGenMockInspector()

        sa_inspection._sql_gen_bind_registered = True  # type: ignore[attr-defined]


__all__ = ["install_offline_sql_gen_mock"]
