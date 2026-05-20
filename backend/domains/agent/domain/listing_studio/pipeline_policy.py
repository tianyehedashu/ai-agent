"""流水线并行层构建策略。"""

from __future__ import annotations

from domains.agent.domain.listing_studio.constants import CAPABILITIES


def build_execution_layers(
    caps_to_run: list[tuple[int, str]],
) -> list[list[tuple[int, str]]]:
    """按依赖关系将能力分组为并行执行层。"""
    cap_ids = {c for _, c in caps_to_run}
    completed: set[str] = set()
    remaining = list(caps_to_run)
    layers: list[list[tuple[int, str]]] = []

    while remaining:
        layer: list[tuple[int, str]] = []
        still_remaining: list[tuple[int, str]] = []
        for order, cap_id in remaining:
            cfg = CAPABILITIES.get(cap_id)
            deps = set(cfg.dependencies) & cap_ids if cfg else set()
            if deps <= completed:
                layer.append((order, cap_id))
            else:
                still_remaining.append((order, cap_id))
        if not layer:
            layers.extend([[(o, c)] for o, c in still_remaining])
            break
        layers.append(layer)
        completed.update(c for _, c in layer)
        remaining = still_remaining

    return layers


__all__ = ["build_execution_layers"]
