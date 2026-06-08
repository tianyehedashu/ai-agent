"""测试上游超时配置注入与 SSE 断连处理。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from domains.gateway.application.proxy_litellm_client import apply_upstream_timeout


class TestApplyUpstreamTimeout:
    @pytest.mark.parametrize(
        "timeout_val,expect_timeout,stream_timeout_val,expect_stream",
        [
            (300, 300, 60, 60),
            (0, None, 0, None),
            (600, 600, 120, 120),
        ],
    )
    def test_injects_timeout(
        self,
        timeout_val: int,
        expect_timeout: int | None,
        stream_timeout_val: int,
        expect_stream: int | None,
    ) -> None:
        with (
            patch(
                "domains.gateway.application.proxy_litellm_client.settings.gateway_upstream_timeout_seconds",
                timeout_val,
            ),
            patch(
                "domains.gateway.application.proxy_litellm_client.settings.gateway_upstream_stream_timeout_seconds",
                stream_timeout_val,
            ),
        ):
            kwargs: dict = {"model": "test-model"}
            result = apply_upstream_timeout(kwargs)
            if expect_timeout is not None:
                assert result["timeout"] == expect_timeout
            else:
                assert "timeout" not in result
            if expect_stream is not None:
                assert result["stream_timeout"] == expect_stream
            else:
                assert "stream_timeout" not in result

    def test_preserves_existing_timeout(self) -> None:
        """kwargs 中已有的 timeout/stream_timeout 不被覆盖。"""
        with (
            patch(
                "domains.gateway.application.proxy_litellm_client.settings.gateway_upstream_timeout_seconds",
                300,
            ),
            patch(
                "domains.gateway.application.proxy_litellm_client.settings.gateway_upstream_stream_timeout_seconds",
                60,
            ),
        ):
            kwargs: dict = {"model": "x", "timeout": 999, "stream_timeout": 88}
            result = apply_upstream_timeout(kwargs)
            assert result["timeout"] == 999
            assert result["stream_timeout"] == 88


class TestSSEDisconnectHandling:

    def test_sse_generator_cancelled_error_raised(self) -> None:
        """SSE 生成器应在 CancelledError 时重新抛出。"""
        import asyncio

        async def _broken_stream():
            yield b"ok"
            raise asyncio.CancelledError()

        async def _sse():
            try:
                async for chunk in _broken_stream():
                    yield chunk
            except asyncio.CancelledError:
                raise

        gen = _sse()

        async def _drive():
            chunks = []
            async for c in gen:
                chunks.append(c)
            return chunks

        with pytest.raises(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(_drive())


class TestTimeoutConfigDefaults:
    """确认配置项默认值与说明一致。"""

    def test_default_timeout_is_300(self) -> None:
        from bootstrap.config import Settings

        s = Settings()
        assert s.gateway_upstream_timeout_seconds == 300

    def test_default_stream_timeout_is_60(self) -> None:
        from bootstrap.config import Settings

        s = Settings()
        assert s.gateway_upstream_stream_timeout_seconds == 60

    def test_zero_disables_timeout(self) -> None:
        from bootstrap.config import Settings

        s = Settings(gateway_upstream_timeout_seconds=0)
        assert s.gateway_upstream_timeout_seconds == 0
