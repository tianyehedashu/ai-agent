"""product_image_gen_task 链式参考图集成逻辑单测（mock ImageGenerator）"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.agent.application.product_image_gen_task_use_case import (
    _generate_images_background,
)
from domains.agent.infrastructure.llm.image_generator import ImageGenerationResult


@pytest.mark.asyncio
async def test_background_chain_uses_slot1_for_slot2() -> None:
    """批量生成时 slot2 应使用 slot1 持久化 URL 作为 reference。"""
    task_id = uuid.uuid4()
    captured_refs: list[str | None] = []

    async def fake_generate(**kwargs: Any) -> ImageGenerationResult:
        captured_refs.append(kwargs.get("reference_image_url"))
        slot_hint = len(captured_refs)
        if slot_hint == 1:
            return ImageGenerationResult(success=True, images=["https://provider/slot1.png"])
        return ImageGenerationResult(success=True, images=["https://provider/slot2.png"])

    image_generator = MagicMock()
    image_generator.generate = AsyncMock(side_effect=fake_generate)

    mock_repo = MagicMock()
    mock_repo.update = AsyncMock()

    mock_image_svc = MagicMock()
    mock_image_svc.persist_generated_image = AsyncMock(
        side_effect=lambda url: f"https://stored/{url.split('/')[-1]}"
    )

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_composer = MagicMock()
    mock_composer.install = MagicMock()
    mock_composer.compose_for_user_id = AsyncMock(return_value=MagicMock())

    prompts = [
        {
            "slot": 1,
            "prompt": "white bg",
            "reference_image_url": "https://source.jpg",
            "provider": "volcengine",
        },
        {
            "slot": 2,
            "prompt": "lifestyle",
            "reference_image_url": "https://source.jpg",
            "provider": "volcengine",
        },
    ]

    with (
        patch(
            "domains.agent.application.product_image_gen_task_use_case.get_session_factory",
            return_value=mock_session_factory,
        ),
        patch(
            "domains.agent.application.product_image_gen_task_use_case.PermissionContextComposer",
            return_value=mock_composer,
        ),
        patch(
            "domains.agent.application.listing_studio_image_factory.create_listing_studio_image_service",
            return_value=mock_image_svc,
        ),
        patch(
            "domains.agent.application.product_image_gen_task_use_case.ProductImageGenTaskRepository",
            return_value=mock_repo,
        ),
    ):
        await _generate_images_background(
            task_id=task_id,
            prompts=prompts,
            image_generator=image_generator,
            user_id=uuid.uuid4(),
        )

    assert captured_refs[0] == "https://source.jpg"
    assert captured_refs[1] == "https://stored/slot1.png"


@pytest.mark.asyncio
async def test_background_single_slot_keeps_explicit_reference() -> None:
    """单槽重生成应保留显式 reference（当前图）。"""
    task_id = uuid.uuid4()
    captured_refs: list[str | None] = []

    async def fake_generate(**kwargs: Any) -> ImageGenerationResult:
        captured_refs.append(kwargs.get("reference_image_url"))
        return ImageGenerationResult(success=True, images=["https://provider/out.png"])

    image_generator = MagicMock()
    image_generator.generate = AsyncMock(side_effect=fake_generate)

    mock_repo = MagicMock()
    mock_repo.update = AsyncMock()
    mock_image_svc = MagicMock()
    mock_image_svc.persist_generated_image = AsyncMock(return_value="https://stored/out.png")
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_composer = MagicMock()
    mock_composer.install = MagicMock()
    mock_composer.compose_for_user_id = AsyncMock(return_value=MagicMock())

    prompts = [
        {
            "slot": 3,
            "prompt": "detail",
            "reference_image_url": "https://current-slot3.jpg",
            "provider": "volcengine",
        },
    ]

    with (
        patch(
            "domains.agent.application.product_image_gen_task_use_case.get_session_factory",
            return_value=mock_session_factory,
        ),
        patch(
            "domains.agent.application.product_image_gen_task_use_case.PermissionContextComposer",
            return_value=mock_composer,
        ),
        patch(
            "domains.agent.application.listing_studio_image_factory.create_listing_studio_image_service",
            return_value=mock_image_svc,
        ),
        patch(
            "domains.agent.application.product_image_gen_task_use_case.ProductImageGenTaskRepository",
            return_value=mock_repo,
        ),
    ):
        await _generate_images_background(
            task_id=task_id,
            prompts=prompts,
            image_generator=image_generator,
            user_id=uuid.uuid4(),
        )

    assert captured_refs == ["https://current-slot3.jpg"]
