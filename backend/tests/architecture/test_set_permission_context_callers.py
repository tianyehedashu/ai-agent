"""生产代码 set_permission_context 调用方白名单（composer / middleware）。"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

_BACKEND = Path(__file__).resolve().parents[2]

_ALLOWED_FILES = {
    "libs/iam/permission_context.py",
    "libs/middleware/permission.py",
    "domains/identity/application/permission_context_composer.py",
}

_PATTERN = re.compile(r"\bset_permission_context\s*\(")


def _py_files() -> list[Path]:
    roots = [_BACKEND / "domains", _BACKEND / "libs"]
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel = path.relative_to(_BACKEND).as_posix()
            if rel.startswith("tests/"):
                continue
            out.append(path)
    return out


@pytest.mark.architecture
def test_set_permission_context_only_allowed_callers() -> None:
    violations: list[str] = []
    for path in _py_files():
        rel = path.relative_to(_BACKEND).as_posix()
        text = path.read_text(encoding="utf-8")
        if not _PATTERN.search(text):
            continue
        if rel not in _ALLOWED_FILES:
            violations.append(rel)
    assert not violations, f"set_permission_context outside whitelist: {violations}"
