"""
Product Info 步骤执行与提示词优化单元测试

覆盖：
- _build_full_input 依赖注入与 user_input 优先级
- _build_context_text 上下文文本构建
- optimize_prompt_for_capability 提示词优化
- run_step 直接渲染+执行
- optimize_prompt 独立优化接口
- OPTIMIZE_SYSTEM_PROMPT(S) 常量完整性
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from domains.agent.application.product_info_capability_runners import (
    _build_context_text,
    optimize_prompt_for_capability,
    render_meta_prompt,
)
from domains.agent.domain.product_info.constants import (
    CAPABILITY_DEPENDENCIES,
    CAPABILITY_IDS,
    OPTIMIZE_SYSTEM_PROMPT,
    OPTIMIZE_SYSTEM_PROMPTS,
)
from domains.agent.infrastructure.models.product_info_job_step import (
    ProductInfoJobStepStatus,
)
from domains.identity.infrastructure.models.user import User
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_CAP_SORT_ORDER: dict[str, int] = {
    "image_analysis": 1,
    "product_link_analysis": 2,
    "competitor_link_analysis": 3,
    "video_script": 4,
    "image_gen_prompts": 5,
}


def _fake_step(
    capability_id: str,
    status: str = ProductInfoJobStepStatus.COMPLETED,
    output_snapshot: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        capability_id=capability_id,
        sort_order=_CAP_SORT_ORDER.get(capability_id, 0),
        status=status,
        output_snapshot=output_snapshot,
    )


def _fake_job(steps: list) -> SimpleNamespace:
    return SimpleNamespace(steps=steps)


# ===========================================================================
# render_meta_prompt
# ===========================================================================


@pytest.mark.unit
class TestRenderMetaPrompt:
    """提示词 {{param}} 占位符渲染"""

    def test_no_placeholders(self):
        assert render_meta_prompt("plain text", {"x": "y"}) == "plain text"

    def test_simple_replace(self):
        out = render_meta_prompt(
            "分析产品 {{product_name}}，链接 {{product_link}}",
            {"product_name": "Widget", "product_link": "https://a.com"},
        )
        assert out == "分析产品 Widget，链接 https://a.com"

    def test_missing_param_replaced_empty(self):
        out = render_meta_prompt("{{x}} and {{y}}", {"x": "a"})
        assert out == "a and "

    def test_dict_value_json_serialized(self):
        out = render_meta_prompt(
            "产品信息：{{product_info}}",
            {
                "product_info": {"name": "X", "price": 99},
            },
        )
        assert "name" in out and "X" in out and "99" in out

    def test_empty_context(self):
        out = render_meta_prompt("{{a}}", {})
        assert out == ""


# ===========================================================================
# _build_context_text
# ===========================================================================


@pytest.mark.unit
class TestBuildContextText:
    """_build_context_text 辅助函数"""

    def test_empty_inputs(self):
        assert _build_context_text({}) == "（无额外输入）"

    def test_scalar_fields(self):
        text = _build_context_text(
            {
                "product_link": "https://a.com",
                "competitor_link": "https://b.com",
                "product_name": "Widget",
                "keywords": "k1, k2",
            }
        )
        assert "产品链接: https://a.com" in text
        assert "竞品链接: https://b.com" in text
        assert "产品名称: Widget" in text
        assert "关键词: k1, k2" in text

    def test_image_urls(self):
        text = _build_context_text({"image_urls": ["https://img1.jpg"]})
        assert "图片 URL 列表" in text
        assert "https://img1.jpg" in text

    def test_structured_deps(self):
        text = _build_context_text(
            {
                "product_info": {"category": "Electronics"},
                "competitor_info": {"name": "Rival"},
                "image_descriptions": [{"desc": "img"}],
                "video_script": {"scenes": 5},
                "prompts": ["p1", "p2"],
            }
        )
        assert "产品信息（前步结果）" in text
        assert "竞品信息（前步结果）" in text
        assert "图片描述（前步结果）" in text
        assert "视频脚本（前步结果）" in text
        assert "图片生成提示词（前步结果）" in text

    def test_unknown_keys_included_as_fallback(self):
        text = _build_context_text(
            {
                "some_new_output": {"x": 1},
                "plain_value": "hello",
            }
        )
        assert "some_new_output（前步结果）" in text
        assert "plain_value: hello" in text

    def test_partial_inputs(self):
        text = _build_context_text({"product_name": "X"})
        assert "产品名称: X" in text
        assert "（无额外输入）" not in text


# ===========================================================================
# _build_full_input (via ProductInfoUseCase)
# ===========================================================================


@pytest.mark.unit
class TestBuildFullInput:
    """依赖注入逻辑：deps 先注入、user_input 后覆盖"""

    def _build(
        self,
        job,
        capability_id: str,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        from domains.agent.application.product_info_use_case import ProductInfoUseCase

        uc = ProductInfoUseCase.__new__(ProductInfoUseCase)
        return uc._build_full_input(job, capability_id, user_input)

    def test_no_deps_returns_user_input(self):
        """无依赖步骤时直接返回 user_input"""
        job = _fake_job([])
        result = self._build(job, "image_analysis", {"product_name": "A"})
        assert result == {"product_name": "A"}

    def test_deps_injected_for_video_script(self):
        """video_script 依赖 product_link_analysis + competitor_link_analysis 输出"""
        job = _fake_job(
            [
                _fake_step("product_link_analysis", output_snapshot={"product_info": {"k": "v"}}),
                _fake_step(
                    "competitor_link_analysis", output_snapshot={"competitor_info": {"c": 1}}
                ),
            ]
        )
        result = self._build(job, "video_script", {"product_name": "X"})
        assert result["product_info"] == {"k": "v"}
        assert result["competitor_info"] == {"c": 1}
        assert result["product_name"] == "X"

    def test_user_input_overrides_deps(self):
        """user_input 中的同名字段应覆盖 deps 注入"""
        job = _fake_job(
            [
                _fake_step(
                    "product_link_analysis",
                    output_snapshot={
                        "product_info": {"auto": True},
                    },
                ),
            ]
        )
        user_edited = {"product_info": {"user_edited": True}}
        result = self._build(job, "video_script", user_edited)
        assert result["product_info"] == {"user_edited": True}

    def test_uncompleted_deps_not_injected(self):
        """未完成的依赖步骤不注入"""
        job = _fake_job(
            [
                _fake_step(
                    "product_link_analysis",
                    status=ProductInfoJobStepStatus.RUNNING,
                    output_snapshot={"product_info": {"should_not": True}},
                ),
            ]
        )
        result = self._build(job, "video_script", {"product_name": "Z"})
        assert "product_info" not in result

    def test_all_prior_steps_injected(self):
        """所有已完成前序步骤的输出均注入"""
        job = _fake_job(
            [
                _fake_step("image_analysis", output_snapshot={"image_descriptions": ["img1"]}),
                _fake_step("product_link_analysis", output_snapshot={"product_info": {"k": "v"}}),
                _fake_step(
                    "competitor_link_analysis", output_snapshot={"competitor_info": {"c": 1}}
                ),
            ]
        )
        result = self._build(job, "video_script", {"product_name": "X"})
        assert result["image_descriptions"] == ["img1"]
        assert result["product_info"] == {"k": "v"}
        assert result["competitor_info"] == {"c": 1}
        assert result["product_name"] == "X"

    def test_later_steps_not_injected(self):
        """后序步骤的输出不注入"""
        job = _fake_job(
            [
                _fake_step("video_script", output_snapshot={"video_script": {"scenes": 5}}),
            ]
        )
        result = self._build(job, "product_link_analysis", {"product_link": "x"})
        assert "video_script" not in result

    def test_deps_with_no_output_snapshot_skipped(self):
        """completed 但 output_snapshot 为 None 的步骤跳过"""
        job = _fake_job(
            [
                _fake_step("product_link_analysis", output_snapshot=None),
            ]
        )
        result = self._build(job, "video_script", {})
        assert result == {}


# ===========================================================================
# optimize_prompt_for_capability
# ===========================================================================


@pytest.mark.unit
class TestOptimizePromptForCapability:
    """提示词优化：用户提示词 + 上下文 → LLM → 优化后的提示词"""

    @pytest.mark.asyncio
    async def test_calls_llm_with_system_and_user_messages(self):
        mock_gw = AsyncMock()
        mock_gw.chat.return_value = SimpleNamespace(content="Optimized prompt")

        result = await optimize_prompt_for_capability(
            "product_link_analysis",
            meta_prompt="分析这个产品",
            context={"product_link": "https://a.com"},
            llm_gateway=mock_gw,
        )
        assert result == "Optimized prompt"
        call_kwargs = mock_gw.chat.call_args
        messages = (
            call_kwargs.kwargs.get("messages")
            or call_kwargs[1].get("messages")
            or call_kwargs[0][0]
        )
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "用户提示词" in messages[1]["content"]
        assert "https://a.com" in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_placeholders_rendered_before_optimization(self):
        """提示词中的 {{param}} 在发送给 LLM 前被 context 值替换"""
        mock_gw = AsyncMock()
        mock_gw.chat.return_value = SimpleNamespace(content="ok")

        await optimize_prompt_for_capability(
            "product_link_analysis",
            "分析产品 {{product_name}}，链接 {{product_link}}",
            {"product_name": "Widget Pro", "product_link": "https://shop.com/p"},
            mock_gw,
        )
        user_content = mock_gw.chat.call_args.kwargs.get("messages", [])[1]["content"]
        assert "Widget Pro" in user_content
        assert "https://shop.com/p" in user_content
        assert "{{product_name}}" not in user_content
        assert "{{product_link}}" not in user_content

    @pytest.mark.asyncio
    async def test_uses_capability_specific_system_prompt(self):
        mock_gw = AsyncMock()
        mock_gw.chat.return_value = SimpleNamespace(content="result")

        await optimize_prompt_for_capability(
            "image_analysis",
            "meta",
            {"image_urls": ["https://img.jpg"]},
            mock_gw,
        )
        messages = (
            mock_gw.chat.call_args.kwargs.get("messages") or mock_gw.chat.call_args[1]["messages"]
        )
        assert messages[0]["content"] == OPTIMIZE_SYSTEM_PROMPTS["image_analysis"]

    @pytest.mark.asyncio
    async def test_falls_back_to_default_system_prompt(self):
        mock_gw = AsyncMock()
        mock_gw.chat.return_value = SimpleNamespace(content="ok")

        await optimize_prompt_for_capability(
            "unknown_cap",
            "meta",
            {},
            mock_gw,
        )
        messages = (
            mock_gw.chat.call_args.kwargs.get("messages") or mock_gw.chat.call_args[1]["messages"]
        )
        assert messages[0]["content"] == OPTIMIZE_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_strips_whitespace(self):
        mock_gw = AsyncMock()
        mock_gw.chat.return_value = SimpleNamespace(content="  hello  \n  ")

        result = await optimize_prompt_for_capability(
            "image_analysis",
            "meta",
            {"image_urls": ["https://x.jpg"]},
            mock_gw,
        )
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_propagates_exception(self):
        mock_gw = AsyncMock()
        mock_gw.chat.side_effect = RuntimeError("LLM down")

        with pytest.raises(RuntimeError, match="LLM down"):
            await optimize_prompt_for_capability(
                "image_analysis",
                "meta",
                {"image_urls": ["https://x.jpg"]},
                mock_gw,
            )


# ===========================================================================
# Constants: OPTIMIZE_SYSTEM_PROMPTS coverage
# ===========================================================================


@pytest.mark.unit
class TestOptimizePromptConstants:
    """提示词优化系统指令常量"""

    def test_default_prompt_non_empty(self):
        assert len(OPTIMIZE_SYSTEM_PROMPT) > 0

    def test_every_capability_has_override(self):
        for cid in CAPABILITY_IDS:
            assert cid in OPTIMIZE_SYSTEM_PROMPTS, f"{cid} 缺少 OPTIMIZE_SYSTEM_PROMPTS"
            assert len(OPTIMIZE_SYSTEM_PROMPTS[cid]) > 0

    def test_all_deps_reference_valid_capabilities(self):
        for cid, deps in CAPABILITY_DEPENDENCIES.items():
            assert cid in CAPABILITY_IDS, f"{cid} 不在 CAPABILITY_IDS 中"
            for dep in deps:
                assert dep in CAPABILITY_IDS, f"依赖 {dep} 不在 CAPABILITY_IDS 中"


# ===========================================================================
# run_step — 直接渲染+执行（需要 DB）
# ===========================================================================


@pytest.mark.unit
class TestRunStep:
    """run_step 渲染提示词后直接执行"""

    async def _create_user(self, db_session) -> User:
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            hashed_password="hashed",
            name="Test",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_run_step_renders_and_executes(self, db_session):
        """run_step 渲染提示词后直接执行 Runner，status 为 completed"""
        user = await self._create_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            from domains.agent.application.product_info_use_case import ProductInfoUseCase

            uc = ProductInfoUseCase(db_session)
            job = await uc.create_job(principal_id=str(user.id), user_id=user.id, title="Test")
            job_id = uuid.UUID(job["id"])

            captured_prompt = []

            async def _mock_runner(_inputs, prompt, _gw, **_kw):
                captured_prompt.append(prompt)
                return {"product_info": {"result": True}}

            with patch.dict(
                "domains.agent.application.product_info_use_case.RUNNERS",
                {"product_link_analysis": _mock_runner},
            ):
                result = await uc.run_step(
                    job_id=job_id,
                    capability_id="product_link_analysis",
                    user_input={"product_link": "https://a.com"},
                    meta_prompt="分析产品 {{product_link}}",
                )

            steps = result.get("steps", [])
            step = next(s for s in steps if s["capability_id"] == "product_link_analysis")
            assert step["status"] == "completed"
            assert step["output_snapshot"] == {"product_info": {"result": True}}
            assert "https://a.com" in captured_prompt[0]
            assert "{{product_link}}" not in captured_prompt[0]
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_run_step_uses_default_prompt_when_none(self, db_session):
        """未提供 meta_prompt 时使用系统默认提示词"""
        user = await self._create_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            from domains.agent.application.product_info_use_case import ProductInfoUseCase

            uc = ProductInfoUseCase(db_session)
            job = await uc.create_job(principal_id=str(user.id), user_id=user.id, title="Default")
            job_id = uuid.UUID(job["id"])

            captured_prompt = []

            async def _mock_runner(_inputs, prompt, _gw, **_kw):
                captured_prompt.append(prompt)
                return {"product_info": {"ok": True}}

            with patch.dict(
                "domains.agent.application.product_info_use_case.RUNNERS",
                {"product_link_analysis": _mock_runner},
            ):
                await uc.run_step(
                    job_id=job_id,
                    capability_id="product_link_analysis",
                    user_input={"product_link": "https://a.com"},
                )

            assert len(captured_prompt[0]) > 0
            assert "https://a.com" in captured_prompt[0]
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_run_step_failure_sets_failed(self, db_session):
        """Runner 异常时 step status → failed"""
        user = await self._create_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            from domains.agent.application.product_info_use_case import ProductInfoUseCase

            uc = ProductInfoUseCase(db_session)
            job = await uc.create_job(principal_id=str(user.id), user_id=user.id, title="Fail")
            job_id = uuid.UUID(job["id"])

            async def _mock_runner(_i, _p, _g, **_kw):
                raise RuntimeError("LLM timeout")

            with (
                patch.dict(
                    "domains.agent.application.product_info_use_case.RUNNERS",
                    {"product_link_analysis": _mock_runner},
                ),
                pytest.raises(RuntimeError, match="LLM timeout"),
            ):
                await uc.run_step(
                    job_id=job_id,
                    capability_id="product_link_analysis",
                    user_input={},
                )

            result = await uc.get_job(job_id)
            step = next(s for s in result["steps"] if s["capability_id"] == "product_link_analysis")
            assert step["status"] == "failed"
            assert "LLM timeout" in step["error_message"]
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_step_serialization_includes_fields(self, db_session):
        """序列化结果中包含 meta_prompt 和 prompt_used"""
        user = await self._create_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            from domains.agent.application.product_info_use_case import ProductInfoUseCase

            uc = ProductInfoUseCase(db_session)
            job = await uc.create_job(principal_id=str(user.id), user_id=user.id, title="Ser")
            job_id = uuid.UUID(job["id"])

            async def _mock_runner(_i, _p, _g, **_kw):
                return {"product_info": {}}

            with patch.dict(
                "domains.agent.application.product_info_use_case.RUNNERS",
                {"product_link_analysis": _mock_runner},
            ):
                result = await uc.run_step(
                    job_id=job_id,
                    capability_id="product_link_analysis",
                    user_input={},
                    meta_prompt="my prompt",
                )

            step = result["steps"][0]
            assert step["meta_prompt"] == "my prompt"
            assert step["prompt_used"] is not None
            assert step["status"] == "completed"
        finally:
            clear_permission_context()
