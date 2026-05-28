#!/usr/bin/env python3
"""为每个 alembic/versions/<name>.py 生成 sql/<name>.up.sql 与 .down.sql（一一对应）。

用法（在 backend/ 目录）:
    uv run python scripts/generate_alembic_sql_files.py
    uv run python scripts/generate_alembic_sql_files.py --force
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

_BACKEND = Path(__file__).resolve().parents[1]
_VERSIONS = _BACKEND / "alembic" / "versions"
_SQL = _BACKEND / "alembic" / "sql"

_REVISION_RE = re.compile(
    r"^revision(?:\s*:\s*str)?\s*=\s*[\"']([^\"']+)[\"']",
    re.MULTILINE,
)
_DOWN_REVISION_RE = re.compile(
    r"^down_revision(?:\s*:\s*str\s*\|\s*None)?\s*=\s*(None|[\"']([^\"']*)[\"'])",
    re.MULTILINE,
)

_SKIP_LINES_PREFIX = (
    "INFO ",
    "BEGIN;",
    "COMMIT;",
)
_SKIP_LINES_CONTAINS = (
    "UPDATE alembic_version",
    "DELETE FROM alembic_version",
    "DROP TABLE alembic_version",
    "Running upgrade",
    "Running downgrade",
)


def _parse_meta(py_path: Path) -> tuple[str, str | None]:
    text = py_path.read_text(encoding="utf-8")
    rev_m = _REVISION_RE.search(text)
    down_m = _DOWN_REVISION_RE.search(text)
    if not rev_m:
        msg = f"revision not found in {py_path.name}"
        raise ValueError(msg)
    revision = rev_m.group(1)
    down_revision: str | None = None
    if down_m and down_m.group(1) != "None":
        down_revision = down_m.group(2) or down_m.group(1)
    return revision, down_revision


def _clean_alembic_sql_output(raw: str) -> str:
    statements: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("--"):
            continue
        if stripped.startswith(_SKIP_LINES_PREFIX):
            continue
        if any(part in stripped for part in _SKIP_LINES_CONTAINS):
            continue
        statements.append(line)
    body = "\n".join(statements).strip()
    if body and not body.endswith(";"):
        body += ";"
    return body + "\n" if body else ""


def _run_alembic_sql(args: list[str]) -> str:
    env = os.environ.copy()
    env["ALEMBIC_SQL_GEN_MOCK"] = "1"
    proc = subprocess.run(
        ["uv", "run", "alembic", *args, "--sql"],
        cwd=_BACKEND,
        capture_output=True,
        check=False,
        env=env,
    )
    stdout = (proc.stdout or b"").decode("utf-8", errors="replace")
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    if proc.returncode != 0:
        err = stderr or stdout or "unknown error"
        raise RuntimeError(err.strip())
    return _clean_alembic_sql_output(stdout)


def _upgrade_range(down: str | None, rev: str) -> str:
    source = down if down else "base"
    return _run_alembic_sql(["upgrade", f"{source}:{rev}"])


def _downgrade_range(rev: str, down: str | None) -> str:
    target = down if down is not None else "base"
    return _run_alembic_sql(["downgrade", f"{rev}:{target}"])


_NO_OP_SQL = "-- 本 revision 无 DDL（no-op）\n"


def _ops_header(
    *,
    stem: str,
    revision: str,
    down_revision: str | None,
    direction: str,
) -> str:
    down_label = down_revision if down_revision else "base"
    return (
        "-- =============================================================================\n"
        "-- 生产运维手工执行 | Alembic 运行时不会加载本文件\n"
        "-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）\n"
        f"-- versions/{stem}.py\n"
        f"-- revision: {revision}\n"
        f"-- down_revision: {down_label}\n"
        f"-- 方向: {direction}\n"
        "--   up.sql   = 升级（从 down_revision 升到 revision）\n"
        "--   down.sql = 回滚（从 revision 退回到 down_revision）\n"
        "-- 执行后请手工维护 alembic_version.version_num\n"
        "-- =============================================================================\n\n"
    )


def _write(
    path: Path,
    content: str,
    *,
    stem: str,
    revision: str,
    down_revision: str | None,
    direction: str,
    force: bool,
) -> bool:
    if path.exists() and not force:
        return False
    if not content.strip():
        content = _NO_OP_SQL
    full = (
        _ops_header(
            stem=stem,
            revision=revision,
            down_revision=down_revision,
            direction=direction,
        )
        + content
    )
    if not full.endswith("\n"):
        full += "\n"
    path.write_text(full, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在的 .up.sql / .down.sql",
    )
    args = parser.parse_args()
    _SQL.mkdir(parents=True, exist_ok=True)

    py_files = sorted(_VERSIONS.glob("*.py"))
    ok = 0
    failed: list[str] = []

    for py_path in py_files:
        stem = py_path.stem
        up_path = _SQL / f"{stem}.up.sql"
        down_path = _SQL / f"{stem}.down.sql"
        try:
            revision, down_revision = _parse_meta(py_path)
            up_sql = _upgrade_range(down_revision, revision)
            wrote_up = _write(
                up_path,
                up_sql,
                stem=stem,
                revision=revision,
                down_revision=down_revision,
                direction="UPGRADE (up.sql)",
                force=args.force,
            )
            try:
                down_sql = _downgrade_range(revision, down_revision)
            except RuntimeError as exc:
                if "NotImplementedError" in str(exc):
                    down_sql = "-- 不可回滚：Python downgrade 为 NotImplementedError\n"
                else:
                    raise
            wrote_down = _write(
                down_path,
                down_sql,
                stem=stem,
                revision=revision,
                down_revision=down_revision,
                direction="DOWNGRADE (down.sql)",
                force=args.force,
            )
            status = []
            if wrote_up:
                status.append("up")
            if wrote_down:
                status.append("down")
            if status:
                print(f"+ {stem}: {', '.join(status)}")
                ok += 1
            else:
                print(f"= {stem}: unchanged")
        except (ValueError, RuntimeError) as exc:
            print(f"! {stem}: {exc}", file=sys.stderr)
            failed.append(stem)

    print(f"\nDone: {ok} updated, {len(failed)} failed, {len(py_files)} total.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
