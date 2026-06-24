"""Chat image generation mode — image_gen creative_mode logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from bootstrap.config import settings
from domains.agent.domain.types import AgentEvent, MessageRole
from domains.agent.infrastructure.llm import create_image_generator
from libs.exceptions import ValidationError

if TYPE_CHECKING:
    from domains.agent.application.chat_use_case import ChatUseCase


class ChatImageGenMixin:
    """image_gen 创作模式：模型解析、能力校验与直连 ImageGenerator。"""

    async def _pick_image_gen_model_ref(
        self: ChatUseCase,
        request_model_ref: str | None,
        session: object,
    ) -> str | None:
        if request_model_ref and str(request_model_ref).strip():
            return str(request_model_ref).strip()
        cfg = session.config if isinstance(getattr(session, "config", None), dict) else {}
        stored = cfg.get("image_gen_model_ref")
        if isinstance(stored, str) and stored.strip():
            return stored.strip()
        return None

    async def _max_reference_images_for_model(self: ChatUseCase, model_key: str) -> int:
        if self._model_catalog is None:
            return 8
        snap = await self._model_catalog.resolve_capabilities(model_key)
        if snap is None:
            return 8
        return snap.max_reference_images if snap.max_reference_images > 0 else 8

    async def _supports_img2img(self: ChatUseCase, model_key: str) -> bool:
        if self._model_catalog is None:
            return True
        snap = await self._model_catalog.resolve_capabilities(model_key)
        if snap is None:
            return True
        return snap.supports_img2img

    async def _run_image_gen_mode(
        self: ChatUseCase,
        *,
        session_id: str,
        message: str,
        session: object,
        model_ref: str | None,
        reference_image_urls: list[str],
        image_gen_strength: float | None,
        is_new_session: bool,
    ) -> AsyncGenerator[AgentEvent, None]:
        allowed = await self._model_resolution.visible_image_gen_system_model_ids()
        picked_ref = await self._pick_image_gen_model_ref(model_ref, session)
        try:
            resolved = await self._model_resolution.resolve_image_gen_model_for_chat(
                picked_ref,
                allowed_image_gen_system_ids=allowed,
            )
        except ValidationError as e:
            yield AgentEvent.error(error=e.message, session_id=session_id)
            return

        persist_ref: str | None = picked_ref
        if persist_ref is None and allowed:
            persist_ref = sorted(allowed)[0]

        model_key_for_caps = persist_ref or ""
        if not model_key_for_caps and resolved.is_system:
            model_key_for_caps = (
                f"{resolved.provider}/{resolved.model}" if resolved.model else resolved.provider
            )

        max_refs = await self._max_reference_images_for_model(model_key_for_caps)
        if len(reference_image_urls) > max_refs:
            yield AgentEvent.error(
                error=f"参考图过多：最多 {max_refs} 张",
                session_id=session_id,
            )
            return

        if reference_image_urls and not await self._supports_img2img(model_key_for_caps):
            yield AgentEvent.error(
                error="当前图像生成模型不支持参考图（图生图）",
                session_id=session_id,
            )
            return

        if resolved.provider not in ("volcengine", "openai"):
            yield AgentEvent.error(
                error=f"对话生图暂不支持提供商: {resolved.provider}",
                session_id=session_id,
            )
            return

        await self.session_use_case.merge_session_config_fragment(
            session_id,
            {
                "creative_mode": "image_gen",
                **({"image_gen_model_ref": persist_ref} if persist_ref else {}),
            },
            flush=False,
        )
        await self.db.flush()
        await self._commit_before_external_wait()

        if is_new_session:
            yield AgentEvent.session_created(session_id)

        ref_url = reference_image_urls[0] if reference_image_urls else None
        prov: Literal["volcengine", "openai"] = (
            "volcengine" if resolved.provider == "volcengine" else "openai"
        )

        yield AgentEvent.thinking(status="image_gen", iteration=1, content="正在生成图像…")
        gen = create_image_generator(settings)
        result = await gen.generate(
            prompt=message,
            provider=prov,
            model=resolved.model,
            reference_image_url=ref_url,
            strength=image_gen_strength,
            api_key_override=resolved.api_key,
            api_base_override=resolved.api_base,
            endpoint_id_override=resolved.endpoint_id,
        )
        if not result.success:
            yield AgentEvent.error(error=result.error or "图像生成失败", session_id=session_id)
            return

        lines: list[str] = []
        for url in result.images:
            lines.append(f"![generated]({url})")
        markdown = "\n\n".join(lines) if lines else "（未返回图像 URL）"

        await self.session_use_case.add_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=markdown,
            metadata={
                "kind": "image_gen",
                "image_urls": result.images,
                "usage": result.usage or {},
            },
        )
        await self.db.commit()

        yield AgentEvent.text(markdown)
        yield AgentEvent.done(
            content=markdown,
            iterations=1,
            tool_iterations=0,
            total_tokens=0,
            usage=None,
            model=resolved.model,
        )
