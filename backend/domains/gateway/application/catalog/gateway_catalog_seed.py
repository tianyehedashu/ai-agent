"""Gateway 系统模型目录种子（JSON）；运行时权威在 DB。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from domains.gateway.domain.catalog.catalog_seed_model import CatalogSeedModel

logger = logging.getLogger(__name__)

DEFAULT_SEED_PATH = Path(__file__).resolve().parents[4] / "seeds" / "gateway-catalog.seed.json"


def default_seed_path() -> Path:
    return DEFAULT_SEED_PATH


def catalog_seed_model_from_dict(raw: dict[str, Any]) -> CatalogSeedModel:
    """将 seed JSON 单条转为 ``CatalogSeedModel``。"""
    return CatalogSeedModel(
        id=str(raw["id"]),
        name=str(raw.get("name") or raw["id"]),
        provider=str(raw["provider"]),
        context_window=int(raw.get("context_window") or 128000),
        input_price=float(raw.get("input_price") or 0.0),
        output_price=float(raw.get("output_price") or 0.0),
        input_cost_per_token=float(raw.get("input_cost_per_token") or 0.0),
        output_cost_per_token=float(raw.get("output_cost_per_token") or 0.0),
        supports_vision=bool(raw.get("supports_vision", False)),
        supports_tools=bool(raw.get("supports_tools", True)),
        supports_reasoning=bool(raw.get("supports_reasoning", False)),
        thinking_param=str(raw.get("thinking_param") or ""),
        supports_json_mode=bool(raw.get("supports_json_mode", True)),
        supports_image_gen=bool(raw.get("supports_image_gen", False)),
        supports_txt2img=bool(raw.get("supports_txt2img", True)),
        supports_img2img=bool(raw.get("supports_img2img", True)),
        supports_video_gen=bool(raw.get("supports_video_gen", False)),
        supports_image_to_video=bool(raw.get("supports_image_to_video", False)),
        max_reference_images=int(raw.get("max_reference_images") or 0),
        litellm_model=str(raw.get("litellm_model") or ""),
        recommended_for=list(raw.get("recommended_for") or []),
        description=str(raw.get("description") or ""),
    )


def load_seed_catalog_models(path: Path | None = None) -> list[CatalogSeedModel]:
    """从 ``gateway-catalog.seed.json`` 加载模型列表；文件不存在则返回空列表。"""
    seed_path = path or default_seed_path()
    if not seed_path.is_file():
        logger.debug("Gateway catalog seed file not found: %s", seed_path)
        return []
    try:
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load gateway catalog seed %s: %s", seed_path, exc)
        return []
    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        logger.warning("Gateway catalog seed %s: missing 'models' array", seed_path)
        return []
    out: list[CatalogSeedModel] = []
    for item in raw_models:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        out.append(catalog_seed_model_from_dict(item))
    return out


def resolve_catalog_seed_models(path: Path | None = None) -> list[CatalogSeedModel]:
    """从 ``gateway-catalog.seed.json`` 加载模型列表。"""
    return load_seed_catalog_models(path)


__all__ = [
    "catalog_seed_model_from_dict",
    "default_seed_path",
    "load_seed_catalog_models",
    "resolve_catalog_seed_models",
]
