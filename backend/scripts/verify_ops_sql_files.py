#!/usr/bin/env python3
"""核对 sql/*.sql 是否与 ``alembic upgrade/downgrade --sql`` 一致。"""

from __future__ import annotations

from pathlib import Path
import re
import sys

# 复用生成脚本的解析与导出
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.generate_alembic_sql_files import (
    _SQL,
    _VERSIONS,
    _clean_alembic_sql_output,
    _downgrade_range,
    _parse_meta,
    _upgrade_range,
)

_HEADER_END = re.compile(r"^-- ={10,}\s*$", re.MULTILINE)


def _strip_ops_header(text: str) -> str:
    # 头尾各一行 `-- ====`，取第二段分隔符之后为 DDL
    parts = _HEADER_END.split(text)
    body = parts[-1] if len(parts) >= 3 else (parts[-1] if len(parts) > 1 else text)
    return body.strip() + ("\n" if body.strip() else "")


def _normalize(sql: str) -> str:
    lines = [ln.rstrip() for ln in sql.strip().splitlines() if ln.strip()]
    return "\n".join(lines)


def main() -> int:
    mismatches: list[str] = []
    missing: list[str] = []
    ok = 0

    for py_path in sorted(_VERSIONS.glob("*.py")):
        stem = py_path.stem
        up_path = _SQL / f"{stem}.up.sql"
        down_path = _SQL / f"{stem}.down.sql"
        if not up_path.is_file() or not down_path.is_file():
            missing.append(stem)
            continue
        try:
            revision, down_revision = _parse_meta(py_path)
            expected_up = _normalize(_upgrade_range(down_revision, revision))
            file_up = _normalize(_strip_ops_header(up_path.read_text(encoding="utf-8")))
            if expected_up != file_up:
                mismatches.append(f"{stem}.up.sql")

            try:
                expected_down = _normalize(_downgrade_range(revision, down_revision))
            except RuntimeError as exc:
                if "NotImplementedError" in str(exc):
                    expected_down = _normalize("-- 不可回滚：Python downgrade 为 NotImplementedError")
                else:
                    raise
            file_down = _normalize(_strip_ops_header(down_path.read_text(encoding="utf-8")))
            if expected_down != file_down:
                mismatches.append(f"{stem}.down.sql")
            if stem not in {m.split(".")[0] for m in mismatches} or not mismatches:
                if f"{stem}.up.sql" not in mismatches and f"{stem}.down.sql" not in mismatches:
                    ok += 1
        except (ValueError, RuntimeError) as exc:
            mismatches.append(f"{stem}: {exc}")

    print(f"OK (与 alembic --sql 一致): {ok}")
    if missing:
        print(f"缺少文件: {len(missing)} -> {missing[:5]}...")
    if mismatches:
        print(f"与重新导出不一致: {len(mismatches)}")
        for m in mismatches[:20]:
            print(f"  - {m}")
        if len(mismatches) > 20:
            print(f"  ... 另有 {len(mismatches) - 20} 项")
    return 1 if missing or mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
