"""
Video Prompt Optimize Use Case - 视频提示词优化用例

利用视觉 LLM 分析用户输入（文字 + 图片），生成优化后的视频生成提示词。
"""

from typing import Any

import httpx

from bootstrap.config import settings
from domains.agent.infrastructure.llm.gateway import LLMGateway
from utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_VIDEO_PROMPT_SYSTEM_TEMPLATE = """\
你是一位专业的 AI 视频生成提示词专家。你的任务是根据用户提供的产品信息（文字描述和/或产品图片），\
生成适合视频生成模型（如 Sora）使用的高质量英文提示词。

## 要求

1. **分析输入**：仔细分析用户提供的文字描述和图片（如果有），理解产品特征、使用场景和卖点。
2. **输出格式**：直接输出英文视频提示词，不要输出其他解释或说明。不要添加 "Here is..." 之类的前缀。
3. **提示词风格**：
   - 使用英文撰写（视频生成模型对英文效果最好）
   - 描述具体的视觉场景、镜头运动、光影效果
   - 突出产品外观特征和功能卖点
   - 包含环境氛围、色调风格等细节
   - 适合 5-15 秒短视频的节奏
4. **结构建议**：
   - 开头：场景设定和氛围
   - 中间：产品展示和功能演示
   - 结尾：品牌感和情感共鸣

## 示例输出

A sleek wireless earbud emerges from its minimalist charging case on a marble surface. \
Soft morning light casts warm highlights across the matte black finish. \
The camera slowly orbits as the earbud levitates and rotates, revealing its ergonomic contours. \
A gentle pulse of light indicates active noise cancellation. \
The scene transitions to a lifestyle shot of someone jogging through a misty park at dawn, \
the earbuds fitting seamlessly. Cinematic shallow depth of field, warm color grading.\
"""


async def _check_image_accessible(url: str, timeout: float = 5.0) -> bool:
    """HEAD 请求预检图片是否可公网访问"""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            resp = await client.head(url)
            return resp.status_code < 400
    except Exception:
        return False


class VideoPromptOptimizeUseCase:
    """视频提示词优化用例"""

    def __init__(self) -> None:
        self.gateway = LLMGateway(settings)

    async def optimize(
        self,
        *,
        user_text: str | None = None,
        image_urls: list[str] | None = None,
        system_prompt: str | None = None,
        marketplace: str = "jp",
    ) -> str:
        """生成优化的视频提示词

        Args:
            user_text: 用户输入的文字描述
            image_urls: 产品图片 URL 列表
            system_prompt: 自定义系统提示词（为空时使用默认）
            marketplace: 目标站点

        Returns:
            优化后的视频生成提示词
        """
        effective_system = system_prompt or DEFAULT_VIDEO_PROMPT_SYSTEM_TEMPLATE

        # 预检图片可达性，过滤不可访问的 URL
        accessible_urls: list[str] = []
        if image_urls:
            for url in image_urls:
                ok = await _check_image_accessible(url)
                if ok:
                    accessible_urls.append(url)
                else:
                    logger.warning("Image URL not accessible, skipping: %s", url[:200])

            if len(accessible_urls) < len(image_urls):
                logger.warning(
                    "Image accessibility: %d/%d accessible",
                    len(accessible_urls),
                    len(image_urls),
                )

        user_content: list[dict[str, Any]] = []
        if user_text:
            user_content.append({"type": "text", "text": f"产品描述：{user_text}"})
        if marketplace:
            user_content.append({"type": "text", "text": f"目标市场：{marketplace}"})
        if accessible_urls:
            for url in accessible_urls:
                user_content.append({"type": "image_url", "image_url": {"url": url}})
            user_content.append(
                {"type": "text", "text": "请根据以上图片和文字描述生成视频提示词。"}
            )
        elif user_text:
            user_content.append({"type": "text", "text": "请根据以上产品描述生成视频提示词。"})

        if not user_content:
            return ""

        has_images = bool(accessible_urls)
        model = settings.vision_model if has_images else settings.default_model

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": effective_system},
            {"role": "user", "content": user_content},
        ]

        logger.info(
            "Optimizing video prompt: model=%s, has_text=%s, "
            "image_count=%d (accessible=%d, original=%d), marketplace=%s",
            model,
            bool(user_text),
            len(accessible_urls),
            len(accessible_urls),
            len(image_urls) if image_urls else 0,
            marketplace,
        )

        if accessible_urls:
            logger.debug(
                "Image URLs being sent to LLM: %s",
                [u[:100] for u in accessible_urls],
            )

        response = await self.gateway.chat(
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=2048,
        )

        result = response.content or ""

        # 如果提供了图片但全部不可达，在结果中提示
        if image_urls and not accessible_urls:
            result = (
                f"[注意：提供的 {len(image_urls)} 张图片均无法访问，"
                "已仅基于文字描述生成。请确认图片链接为公网可直接访问的 URL。]\n\n" + result
            )

        return result
