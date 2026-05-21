"""Migrate flat gateway management test URLs to /teams/{team_id}/*."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEAM_RESOURCES = (
    "logs",
    "keys",
    "credentials",
    "models",
    "budgets",
    "routes",
    "alerts",
    "dashboard",
    "pricing",
    "features",
    "admin",
)

HEADER_TEAM_RE = re.compile(
    r'^(?P<indent>\s*)(?P<var>\w+)\s*=\s*\{\*\*(?P<base>\w+),\s*"X-Team-Id":\s*str\((?P<team>[^)]+)\)\}'
)


def migrate_content(text: str) -> str:
    lines = text.splitlines(keepends=True)
    active_team: str | None = None
    out: list[str] = []

    for line in lines:
        header_match = HEADER_TEAM_RE.match(line.rstrip("\n"))
        if header_match:
            active_team = header_match.group("team")
            base = header_match.group("base")
            indent = header_match.group("indent")
            var = header_match.group("var")
            out.append(f'{indent}{var} = {base}\n')
            continue

        if active_team and ('"/api/v1/gateway/' in line or "'/api/v1/gateway/" in line):
            for resource in TEAM_RESOURCES:
                old_dq = f'"/api/v1/gateway/{resource}'
                old_sq = f"'/api/v1/gateway/{resource}"
                new = f'f"/api/v1/gateway/teams{{{active_team}}}/{resource}'
                if old_dq in line:
                    line = line.replace(old_dq, new)
                if old_sq in line:
                    line = line.replace(old_sq, new.replace('"', "'"))

        out.append(line)

        # Reset on blank line after long gap? keep active_team for whole test method
        if line.strip().startswith("async def test_") or line.strip().startswith("def test_"):
            active_team = None

    return "".join(out)


def migrate_file(rel: str) -> None:
    path = ROOT / rel
    original = path.read_text(encoding="utf-8")
    updated = migrate_content(original)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print(f"updated {rel}")


def main() -> None:
    for rel in (
        "tests/integration/api/test_gateway_management_api.py",
        "tests/integration/api/test_openai_compat_api.py",
        "tests/integration/api/test_credential_upstream_probe_api.py",
        "tests/integration/api/test_gateway_bridge_attribution.py",
        "tests/unit/tenancy/test_gateway_viewer_readonly.py",
    ):
        migrate_file(rel)


if __name__ == "__main__":
    main()
