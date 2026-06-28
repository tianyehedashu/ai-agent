"""上游探测模型 ID → 实际 chat/completions 接受名称的规范化（纯函数，无 I/O）。

某些 OpenAI 兼容上游（如 cmecloud）的 ``GET /v1/models`` 返回的模型 ID
与其 ``POST /v1/chat/completions`` 接受的 ``model`` 名称在大小写 / 分隔符上
不一致。  本模块维护一份已知映射，在批量导入时自动纠正 ``real_model`` 落库值。

映射键统一 **小写** 匹配；值为上游 chat API 精确接受的名称。
"""

from __future__ import annotations

# (lowercase probe id) → (upstream chat API accepted name)
_NORMALIZE_MAP: dict[str, str] = {
    "minimax-m2-5": "MiniMax-M2.5",
    "minimax-m2.5": "MiniMax-M2.5",
}


def normalize_upstream_model_id(model_id: str) -> str:
    """将上游探测到的 model ID 规范化为 chat API 接受的实际名称。

    - 已知映射 → 返回规范名；
    - 未知 → 原样返回（不做任何大小写变换）。
    """
    stripped = model_id.strip()
    if not stripped:
        return stripped
    return _NORMALIZE_MAP.get(stripped.lower(), stripped)


__all__ = ["normalize_upstream_model_id"]
