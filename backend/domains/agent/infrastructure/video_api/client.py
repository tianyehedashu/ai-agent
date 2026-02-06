"""
Video API Client - 视频生成 API 客户端

与 GIIKIN 等视频生成厂商的 API 交互。
"""

import asyncio
from typing import Any

import httpx

from bootstrap.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class VideoAPIError(Exception):
    """视频 API 错误"""

    def __init__(self, message: str, code: int | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class VideoAPIClient:
    """视频生成 API 客户端

    支持 GIIKIN API：
    - Token 获取（OAuth2 client_credentials）
    - 任务提交
    - 状态轮询

    配置通过环境变量：
    - GIIKIN_CLIENT_ID: OAuth2 客户端 ID
    - GIIKIN_CLIENT_SECRET: OAuth2 客户端密钥
    - GIIKIN_BASE_URL: API 基础 URL（默认 https://openapi.giikin.com）
    """

    # API 端点
    DEFAULT_BASE_URL = "https://openapi.giikin.com"
    TOKEN_ENDPOINT = "/oauth2/client_token"
    SUBMIT_ENDPOINT = "/third/material-composer/v1/openapi/workflow/run"
    QUERY_ENDPOINT = "/third/material-composer/v1/openapi/workflow/query"

    # 工作流类型
    WORKFLOW_TYPE = "amazon.material.image2video"

    # 状态码映射
    STATUS_RUNNING = 1
    STATUS_COMPLETED = 2
    STATUS_FAILED = 3
    STATUS_CANCELED = 4
    STATUS_TERMINATED = 5
    STATUS_CONTINUED_AS_NEW = 6
    STATUS_TIMED_OUT = 7

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
    ):
        """初始化客户端

        Args:
            client_id: OAuth2 客户端 ID（默认从环境变量读取）
            client_secret: OAuth2 客户端密钥（默认从环境变量读取）
            base_url: API 基础 URL（默认从环境变量读取）
        """
        self.client_id = client_id or getattr(settings, "giikin_client_id", None)
        self.client_secret = client_secret or getattr(settings, "giikin_client_secret", None)
        self.base_url = (
            base_url or getattr(settings, "giikin_base_url", None) or self.DEFAULT_BASE_URL
        )

        self._token: str | None = None
        self._token_expires_at: float = 0

    async def _get_token(self) -> str:
        """获取 OAuth2 Token

        使用 client_credentials 流程获取 token。
        Token 有效期 7200 秒（2 小时），会自动缓存复用。

        Returns:
            访问令牌

        Raises:
            VideoAPIError: 获取 token 失败
        """
        import time

        # 检查缓存的 token 是否有效（提前 5 分钟过期）
        if self._token and time.time() < self._token_expires_at - 300:
            return self._token

        if not self.client_id or not self.client_secret:
            raise VideoAPIError(
                "Missing GIIKIN credentials. Please set GIIKIN_CLIENT_ID and GIIKIN_CLIENT_SECRET.",
                code=401,
            )

        url = f"{self.base_url}{self.TOKEN_ENDPOINT}"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        # 重试逻辑（指数退避）
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(url, params=params)
                    data = response.json()

                    if data.get("code") == 200:
                        # GIIKIN 使用非标准字段 client_token
                        token_data = data.get("data", {})
                        self._token = token_data.get("client_token")
                        # Token 有效期 7200 秒
                        expires_in = token_data.get("expires_in", 7200)
                        self._token_expires_at = time.time() + expires_in

                        if not self._token:
                            raise VideoAPIError(
                                "Token response missing client_token",
                                code=response.status_code,
                                details=data,
                            )

                        logger.debug("Obtained GIIKIN token, expires in %d seconds", expires_in)
                        return self._token

                    raise VideoAPIError(
                        f"Token request failed: {data.get('message', 'Unknown error')}",
                        code=data.get("code"),
                        details=data,
                    )

            except httpx.HTTPError as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt  # 1, 2, 4 秒
                    logger.warning(
                        "Token request failed (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1,
                        max_retries,
                        wait_time,
                        e,
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise VideoAPIError(
                        f"Token request failed after {max_retries} attempts: {e}",
                        code=500,
                    ) from e

        raise VideoAPIError("Token request failed: max retries exceeded")

    async def submit(
        self,
        prompt: str,
        reference_images: list[str],
        marketplace: str = "jp",
        model: str = "openai::sora1.0",
        duration: int = 5,
        flag: str = "video_complete",
        creator_id: int | None = None,
    ) -> tuple[str, str]:
        """提交视频生成任务

        Args:
            prompt: 完整的视频生成提示词（包含镜头、过渡、技术要求）
            reference_images: 参考图片 URL 列表
            marketplace: 目标站点（jp, us, de 等），影响视频文案语言
            model: 视频生成模型 (openai::sora1.0, openai::sora2.0)
            duration: 视频时长（秒）
            flag: 视频标识（默认 video_complete）
            creator_id: 操作用户 ID（厂商追踪用，默认从配置读取）

        Returns:
            (workflow_id, run_id) 元组

        Raises:
            VideoAPIError: 提交失败
        """
        token = await self._get_token()
        url = f"{self.base_url}{self.SUBMIT_ENDPOINT}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # 获取 creator_id，优先使用传入值，否则从配置读取，最后使用默认值
        actual_creator_id = creator_id
        if actual_creator_id is None:
            actual_creator_id = getattr(settings, "giikin_creator_id", None)
        if actual_creator_id is None:
            actual_creator_id = 0  # 默认值

        # 构建请求体 - 根据 API 规范
        payload = {
            "workflow_type": self.WORKFLOW_TYPE,
            "inputs": {
                "callback_url": "NONE",  # 禁用回调，使用轮询
                "creator_id": actual_creator_id,
                "video_handle": {
                    "generate_videos": [
                        {
                            "flag": flag,
                            "config": {
                                "prompt": prompt,
                                "model": model,
                                "duration": duration,
                            },
                            "image_urls": reference_images or [],
                        }
                    ]
                },
            },
        }

        logger.debug(
            "Submitting video generation task: model=%s, duration=%ds, images=%d",
            model,
            duration,
            len(reference_images),
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            data = response.json()

            if data.get("code") == 200:
                result = data.get("data", {})
                workflow_id = result.get("workflowId") or result.get("workflow_id")
                run_id = result.get("runId") or result.get("run_id")

                if not workflow_id or not run_id:
                    raise VideoAPIError(
                        "Submit response missing workflow_id or run_id",
                        code=response.status_code,
                        details=data,
                    )

                logger.info(
                    "Video generation task submitted: workflow_id=%s, run_id=%s, model=%s",
                    workflow_id,
                    run_id,
                    model,
                )
                return workflow_id, run_id

            raise VideoAPIError(
                f"Submit failed: {data.get('message', 'Unknown error')}",
                code=data.get("code"),
                details=data,
            )

    async def poll(
        self,
        workflow_id: str,
        run_id: str,
    ) -> tuple[int, dict[str, Any]]:
        """查询任务状态

        Args:
            workflow_id: 工作流 ID
            run_id: 运行 ID

        Returns:
            (status, result) 元组
            - status: 状态码（1=运行中, 2=完成, 3=失败, 等）
            - result: 完整结果（包含 video_url 等）

        Raises:
            VideoAPIError: 查询失败
        """
        token = await self._get_token()
        url = f"{self.base_url}{self.QUERY_ENDPOINT}"

        headers = {
            "Authorization": f"Bearer {token}",
        }

        params = {
            "type": self.WORKFLOW_TYPE,
            "workflow_id": workflow_id,
            "run_id": run_id,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, headers=headers)
            data = response.json()

            if data.get("code") == 200:
                result = data.get("data", {})
                status = result.get("status", 0)

                logger.debug(
                    "Poll result: workflow_id=%s, status=%d",
                    workflow_id,
                    status,
                )

                return status, result

            raise VideoAPIError(
                f"Poll failed: {data.get('message', 'Unknown error')}",
                code=data.get("code"),
                details=data,
            )

    async def poll_until_complete(
        self,
        workflow_id: str,
        run_id: str,
        initial_delay: int = 240,
        poll_interval: int = 30,
        max_wait: int = 900,
    ) -> dict[str, Any]:
        """轮询直到任务完成

        Args:
            workflow_id: 工作流 ID
            run_id: 运行 ID
            initial_delay: 初始等待时间（秒，默认 4 分钟）
            poll_interval: 轮询间隔（秒，默认 30 秒）
            max_wait: 最大等待时间（秒，默认 15 分钟）

        Returns:
            完整结果

        Raises:
            VideoAPIError: 任务失败或超时
        """
        import time

        # 初始等待
        logger.info(
            "Waiting %d seconds before first poll for workflow_id=%s",
            initial_delay,
            workflow_id,
        )
        await asyncio.sleep(initial_delay)

        start_time = time.time()

        while time.time() - start_time < max_wait:
            status, result = await self.poll(workflow_id, run_id)

            if status == self.STATUS_COMPLETED:
                logger.info("Video generation completed: workflow_id=%s", workflow_id)
                return result

            if status in (
                self.STATUS_FAILED,
                self.STATUS_CANCELED,
                self.STATUS_TERMINATED,
                self.STATUS_TIMED_OUT,
            ):
                raise VideoAPIError(
                    f"Video generation failed with status {status}",
                    code=status,
                    details=result,
                )

            logger.debug(
                "Video generation in progress: workflow_id=%s, status=%d",
                workflow_id,
                status,
            )
            await asyncio.sleep(poll_interval)

        raise VideoAPIError(
            f"Timeout waiting for video generation: workflow_id={workflow_id}",
            code=self.STATUS_TIMED_OUT,
        )

    @staticmethod
    def extract_video_url(result: dict[str, Any]) -> str | None:
        """从结果中提取视频 URL

        支持多种可能的数据结构：
        - result.result.video_handle.generate_videos[0].video_url
        - result.video_handle.generate_videos[0].video_url
        - result.generate_videos[0].video_url
        - result.video_url

        Args:
            result: poll 返回的完整结果

        Returns:
            视频 URL 或 None
        """
        if not result:
            return None

        # 尝试多种路径
        paths_to_try = [
            # 标准路径: result.result.video_handle.generate_videos[0].video_url
            lambda r: r.get("result", {})
            .get("video_handle", {})
            .get("generate_videos", [{}])[0]
            .get("video_url"),
            # 无 result 包装: result.video_handle.generate_videos[0].video_url
            lambda r: r.get("video_handle", {}).get("generate_videos", [{}])[0].get("video_url"),
            # 直接 generate_videos: result.generate_videos[0].video_url
            lambda r: r.get("generate_videos", [{}])[0].get("video_url"),
            # 直接 video_url: result.video_url
            lambda r: r.get("video_url"),
            # result.result.video_url
            lambda r: r.get("result", {}).get("video_url"),
        ]

        for path_fn in paths_to_try:
            try:
                url = path_fn(result)
                if url and isinstance(url, str) and url.startswith("http"):
                    return url
            except (AttributeError, IndexError, KeyError, TypeError):
                continue

        # 如果都失败了，记录日志以便调试
        logger.warning("Could not extract video_url from result: %s", result)
        return None
