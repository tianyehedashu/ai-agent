"""
Product Info Capability Runners - 产品信息原子能力执行器

每个能力：接收完整输入与提示词，调用 LLM，返回结构化 output_snapshot。
应用层编排，不使用 LangGraph。通用执行器 _run_capability 从 CapabilityConfig 读取参数。

元提示词支持 {{param}} 占位符，在生成提示词前用 context 中的值替换。
"""

from collections.abc import Callable
import json
import re
from typing import Any

from domains.agent.domain.product_info.constants import (
    CAPABILITIES,
    CAPABILITIES_REQUIRING_VISION,
    CAPABILITY_IMAGE_ANALYSIS,
    CAPABILITY_IMAGE_GEN_PROMPTS,
    CAPABILITY_VIDEO_SCRIPT,
    OPTIMIZE_SYSTEM_PROMPT,
    OPTIMIZE_SYSTEM_PROMPTS,
    RUNNER_JSON_SYSTEM_PROMPT,
    CapabilityConfig,
)
from utils.logging import get_logger

logger = get_logger(__name__)


def _value_to_str(val: Any) -> str:
    """将 context 值转为可嵌入提示词的字符串。"""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False, indent=2)
    return str(val)


def render_meta_prompt(meta_prompt: str, context: dict[str, Any]) -> str:
    """
    将元提示词中的 {{param}} 占位符替换为 context 中的实际值。

    示例：meta_prompt="分析产品 {{product_name}}，链接 {{product_link}}"
         context={"product_name": "XX", "product_link": "https://..."}
         -> "分析产品 XX，链接 https://..."
    """
    if not meta_prompt or "{{" not in meta_prompt:
        return meta_prompt
    result = meta_prompt
    for key, value in context.items():
        placeholder = "{{" + key + "}}"
        if placeholder in result:
            result = result.replace(placeholder, _value_to_str(value))
    # 未提供的占位符替换为空
    result = re.sub(r"\{\{(\w+)\}\}", "", result)
    return result


async def optimize_prompt_for_capability(
    capability_id: str,
    meta_prompt: str,
    context: dict[str, Any],
    llm_gateway: Any,
    model_override: dict[str, Any] | None = None,
) -> str:
    """可选的提示词优化：LLM 将用户提示词改写为更详细的执行提示词。"""
    resolved_meta = render_meta_prompt(meta_prompt, context)
    system_prompt = OPTIMIZE_SYSTEM_PROMPTS.get(capability_id, OPTIMIZE_SYSTEM_PROMPT)
    context_text = _build_context_text(context)
    text_content = f"用户提示词：\n{resolved_meta}\n\n当前上下文：\n{context_text}"

    image_urls: list[str] = context.get("image_urls") or []
    if capability_id in CAPABILITIES_REQUIRING_VISION:
        if not image_urls:
            raise ValueError("图片分析需要至少提供一张图片（image_urls 为空）")
        user_content: str | list[dict[str, Any]] = _build_vision_user_content(text_content, image_urls)
    else:
        user_content = text_content

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    extra = _build_model_kwargs(model_override)
    try:
        response = await llm_gateway.chat(messages=messages, temperature=0.3, max_tokens=4096, **extra)
        content = (response.content or "").strip()
        if getattr(response, "finish_reason", None) == "length":
            logger.warning(
                "optimize_prompt_for_capability(%s) 可能被 max_tokens 截断，建议检查结果",
                capability_id,
            )
        return content
    except Exception as e:
        logger.exception("optimize_prompt_for_capability failed for %s: %s", capability_id, e)
        raise


def _build_model_kwargs(model_override: dict[str, Any] | None) -> dict[str, Any]:
    """从 model_override 构建传给 llm_gateway.chat 的额外参数"""
    if not model_override:
        return {}
    kwargs: dict[str, Any] = {}
    if model_override.get("model"):
        kwargs["model"] = model_override["model"]
    if model_override.get("api_key"):
        kwargs["api_key"] = model_override["api_key"]
    if model_override.get("api_base"):
        kwargs["api_base"] = model_override["api_base"]
    return kwargs


_USER_INPUT_KEYS = {"product_link", "competitor_link", "product_name", "keywords", "image_urls"}

_PRIOR_STEP_LABELS: dict[str, str] = {
    "product_info": "产品信息",
    "competitor_info": "竞品信息",
    "image_descriptions": "图片描述",
    "video_script": "视频脚本",
    "prompts": "图片生成提示词",
}


def _build_context_text(inputs: dict[str, Any]) -> str:
    """将输入转为 LLM 可读的上下文字符串"""
    parts: list[str] = []

    if inputs.get("product_link"):
        parts.append(f"产品链接: {inputs['product_link']}")
    if inputs.get("competitor_link"):
        parts.append(f"竞品链接: {inputs['competitor_link']}")
    if inputs.get("product_name"):
        parts.append(f"产品名称: {inputs['product_name']}")
    if inputs.get("keywords"):
        parts.append(f"关键词: {inputs['keywords']}")
    if inputs.get("image_urls"):
        parts.append(f"图片 URL 列表: {inputs['image_urls']}")

    for key, label in _PRIOR_STEP_LABELS.items():
        val = inputs.get(key)
        if val:
            parts.append(f"{label}（前步结果）:\n{json.dumps(val, ensure_ascii=False, indent=2)}")

    skip_keys = _USER_INPUT_KEYS | set(_PRIOR_STEP_LABELS) | {"raw"}
    for key, val in inputs.items():
        if key in skip_keys or val is None:
            continue
        if isinstance(val, (dict, list)):
            parts.append(f"{key}（前步结果）:\n{json.dumps(val, ensure_ascii=False, indent=2)}")
        else:
            parts.append(f"{key}: {val}")

    return "\n".join(parts) if parts else "（无额外输入）"


def _build_vision_user_content(
    text: str, image_urls: list[str],
) -> list[dict[str, Any]]:
    """构建 Vision 多模态 content：text + image_url blocks，让 LLM 真正看到图片"""
    parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for url in image_urls:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts


_RESPONSE_FORMAT_JSON: dict[str, str] = {"type": "json_object"}


def _parse_json_response(text: str) -> Any:
    """从 LLM 响应中提取 JSON，兼容 markdown 代码块包裹的情况。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if "```" not in text:
        return None
    for start_char, end_char in ("{", "}"), ("[", "]"):
        start = text.find(start_char)
        end = text.rfind(end_char) + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                continue
    return None


def _unwrap_or_use(data: Any, expected_key: str) -> Any:
    """若 data 是包含 expected_key 的 dict，返回该值；否则返回 data 本身。

    处理 json_object 模式下 LLM 可能将结果包裹在顶层 key 中的情况。
    """
    if isinstance(data, dict) and expected_key in data:
        return data[expected_key]
    return data


async def _run_capability(
    config: CapabilityConfig,
    inputs: dict[str, Any],
    prompt: str,
    llm_gateway: Any,
    model_override: dict[str, Any] | None = None,
    post_process: Callable[[Any, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """通用 Runner：根据 CapabilityConfig 构建消息、调用 LLM、解析 JSON、包装输出。"""
    context = _build_context_text(inputs)
    user_content: str | list[dict[str, Any]] = f"{prompt}\n\n当前输入：\n{context}"

    if "vision" in config.required_features:
        image_urls: list[str] = inputs.get("image_urls") or []
        if not image_urls:
            raise ValueError("需要至少提供一张图片（image_urls 为空）")
        user_content = _build_vision_user_content(user_content, image_urls)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": RUNNER_JSON_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    extra = _build_model_kwargs(model_override)
    try:
        response = await llm_gateway.chat(
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            response_format=_RESPONSE_FORMAT_JSON,
            **extra,
        )
        text = (response.content or "").strip()
        data = _parse_json_response(text)

        if post_process:
            return post_process(data, text)

        if isinstance(data, dict):
            return {config.output_key: _unwrap_or_use(data, config.output_key)}
        return {config.output_key: {"raw_text": text}, "raw": text}
    except Exception as e:
        logger.exception("%s failed: %s", config.id, e)
        raise


def _normalize_image_description_item(item: Any) -> dict[str, Any]:
    """将单条图片描述归一为 {description: str}，兼容 content/description/纯字符串/对象。"""
    if item is None:
        return {"description": ""}
    if isinstance(item, str):
        return {"description": item}
    if isinstance(item, dict):
        desc = (
            item.get("description")
            or item.get("content")
            or item.get("text")
            or (json.dumps(item, ensure_ascii=False) if item else "")
        )
        return {"description": desc if isinstance(desc, str) else str(desc)}
    return {"description": str(item)}


def _post_process_image_analysis(data: Any, text: str) -> dict[str, Any]:
    """image_analysis 后处理：兼容 list/dict/None 多种响应格式，并归一化 description。"""
    if data is None:
        return {"image_descriptions": [{"description": text or ""}], "raw": text}
    if isinstance(data, list):
        normalized = [_normalize_image_description_item(x) for x in data]
    else:
        descs = _unwrap_or_use(data, "image_descriptions")
        if isinstance(descs, list):
            normalized = [_normalize_image_description_item(x) for x in descs]
        else:
            normalized = [_normalize_image_description_item(data)]
    # 若全部为空且存在原始响应，用 raw 填到第一条，避免界面只显示「—」
    if text and all(not (n.get("description") or "").strip() for n in normalized):
        if normalized:
            normalized[0]["description"] = text
        else:
            normalized = [{"description": text}]
    return {"image_descriptions": normalized, "raw": text}


def _post_process_video_script(data: Any, text: str) -> dict[str, Any]:
    """video_script 后处理：确保输出含 shots（分镜展示）和 video_prompt（Sora 可用）。

    兼容三种 LLM 输出：
    - JSON 对象 {"shots": [...], "video_prompt": "..."} （理想）
    - JSON 数组 [{镜号, ...}, ...] （旧格式向后兼容）
    - 纯文本（降级）
    """
    shots: list[dict[str, Any]] = []
    video_prompt: str = ""

    if isinstance(data, dict):
        raw_shots = data.get("shots") or data.get("video_script")
        if isinstance(raw_shots, list):
            shots = raw_shots
        vp = data.get("video_prompt", "")
        video_prompt = " ".join(str(p) for p in vp) if isinstance(vp, list) else str(vp or "")
    elif isinstance(data, list):
        shots = data

    if not video_prompt.strip() and shots:
        prompts = [
            str(s.get("prompt", ""))
            for s in shots
            if isinstance(s, dict) and s.get("prompt")
        ]
        video_prompt = " ".join(prompts)

    if not video_prompt.strip():
        video_prompt = text

    script_output: Any = {"shots": shots} if shots else {"raw_text": text}
    return {"video_script": script_output, "video_prompt": video_prompt}


def _post_process_image_gen(data: Any, text: str) -> dict[str, Any]:
    """image_gen_prompts 后处理：补齐到 8 条，第 1 条加白底。"""
    prompts: list[str]
    if isinstance(data, list):
        prompts = [str(p) for p in data]
    elif isinstance(data, dict):
        prompts_list = _unwrap_or_use(data, "prompts")
        prompts = [str(p) for p in prompts_list] if isinstance(prompts_list, list) else [text]
    else:
        prompts = [text]

    if len(prompts) > 8:
        prompts = prompts[:8]
    elif len(prompts) < 8:
        prompts += [""] * (8 - len(prompts))

    if prompts and "white" not in prompts[0].lower() and "白底" not in prompts[0]:
        prompts[0] = (
            "Product on plain white background, centered, studio lighting, e-commerce. "
            + prompts[0]
        )
    return {"prompts": prompts}


def _make_runner(
    config: CapabilityConfig,
    post_process: Callable[[Any, str], dict[str, Any]] | None = None,
) -> Any:
    """创建 Runner 闭包，保持 (inputs, prompt, llm_gateway, model_override) 签名。"""

    async def _run(
        inputs: dict[str, Any],
        prompt: str,
        llm_gateway: Any,
        model_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await _run_capability(
            config, inputs, prompt, llm_gateway, model_override, post_process,
        )

    return _run


_POST_PROCESSORS: dict[str, Callable[[Any, str], dict[str, Any]]] = {
    CAPABILITY_IMAGE_ANALYSIS: _post_process_image_analysis,
    CAPABILITY_VIDEO_SCRIPT: _post_process_video_script,
    CAPABILITY_IMAGE_GEN_PROMPTS: _post_process_image_gen,
}

RUNNERS: dict[str, Any] = {
    cap_id: _make_runner(cfg, _POST_PROCESSORS.get(cap_id))
    for cap_id, cfg in CAPABILITIES.items()
}
