"""
Identity API - 用户认证接口
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bootstrap.config import settings
from domains.identity.application import UserUseCase
from domains.identity.infrastructure.authentication import (
    auth_backend,
    current_active_user,
    fastapi_users,
)
from domains.identity.presentation.deps import get_current_user
from domains.identity.presentation.schemas import (
    CurrentUser,
    RefreshTokenRequest,
    SsoExchangeRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserRead,
    UserUpdate,
)
from libs.identity_bridge_deps import get_user_use_case
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# FastAPI Users routers（保留 /jwt/logout）
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
    tags=["Authentication"],
)
if settings.allow_register:
    router.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        tags=["Authentication"],
    )


@router.get("/me")
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """获取当前用户信息（需认证）。"""
    logger.info("GET /api/v1/auth/me - user_id=%s", current_user.id)
    return current_user


@router.put("/me", response_model=UserRead)
async def update_me(
    data: UserUpdate,
    user_service: Annotated[UserUseCase, Depends(get_user_use_case)],
    user=Depends(current_active_user),
) -> UserRead:
    """更新当前用户"""
    updated = await user_service.update_user(
        user_id=str(user.id),
        name=data.name,
        avatar_url=data.avatar_url,
        vendor_creator_id=data.vendor_creator_id,
    )
    return UserRead.model_validate(updated, from_attributes=True)


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""

    old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=100)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: ChangePasswordRequest,
    user_service: Annotated[UserUseCase, Depends(get_user_use_case)],
    user=Depends(current_active_user),
) -> None:
    """修改密码"""
    await user_service.change_password(
        user_id=str(user.id),
        old_password=request.old_password,
        new_password=request.new_password,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    """退出登录（本地 JWT 由前端清除；SSO 登出走 giikin-iam）。"""
    return None


# =============================================================================
# SSO 换票端点（旁路 HiGress 未透传 Set-Cookie 到 gateway.giimallai.com 的问题）
# =============================================================================


@router.post("/sso-exchange")
async def sso_ticket_exchange(data: SsoExchangeRequest, response: Response) -> JSONResponse:
    """SSO ticket 换票：调用 IAM 登录 API，将 guard_token 重新设置到网关域。

    HiGress 在 proxy IAM API 响应时未透传 Set-Cookie，导致 guard_token 的
    Domain=.giikin.com 在 gateway.giimallai.com 下无法被浏览器接受。
    本端点从 IAM 响应中提取 guard_token，以无 Domain 的方式重新 Set-Cookie，
    使其落在 gateway.giimallai.com 域下，后续请求 HiGress 可正常注入 X-Giikin-*。
    """
    import httpx

    iam_payload = {
        "grantType": "company_sso",
        "ticket": data.ticket,
        "tenantId": data.tenant_id,
        "source": "company_sso",
        "callbackOrigin": f"http://gateway.giimallai.com",
        "clientId": data.client_id,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            iam_resp = await client.post(
                "http://gateway.giimallai.com/api/auth/login",
                json=iam_payload,
                headers={"Content-Type": "application/json"},
            )
    except httpx.RequestError as exc:
        logger.error("[SSO exchange] IAM login request failed: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"detail": "无法连接 SSO 认证服务，请稍后重试"},
        )

    if iam_resp.status_code != 200:
        logger.error(
            "[SSO exchange] IAM login returned %d: %s",
            iam_resp.status_code,
            iam_resp.text[:500],
        )
        return JSONResponse(
            status_code=502,
            content={"detail": f"SSO 认证失败（{iam_resp.status_code}），请重试"},
        )

    # 从 IAM 响应中提取 guard_token（Domain=.giikin.com），
    # 以无 Domain 的方式重新 Set-Cookie 到 gateway.giimallai.com
    set_cookie_headers = iam_resp.headers.get("set-cookie", "")
    guard_token_value = None
    for cookie_str in (set_cookie_headers or "").split(","):
        cookie_str = cookie_str.strip()
        if cookie_str.startswith("guard_token="):
            guard_token_value = cookie_str.split(";")[0].split("=", 1)[1]
            break

    if guard_token_value:
        response.set_cookie(
            key="guard_token",
            value=guard_token_value,
            path="/",
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=2592000,  # 30 天，与 IAM 默认一致
        )
        logger.info("[SSO exchange] guard_token re-set on gateway domain")
    else:
        logger.warning("[SSO exchange] IAM response missing guard_token Set-Cookie")

    return JSONResponse(content={"ok": True})


# =============================================================================
# Token 端点（增强版登录 + Refresh）
# =============================================================================


@router.post("/token", response_model=TokenResponse)
async def login_for_token_pair(
    login_data: Annotated[UserLogin, Body()],
    user_use_case: Annotated[UserUseCase, Depends(get_user_use_case)],
) -> TokenResponse:
    """登录并获取 Token 对（access_token + refresh_token）。

    替代 /jwt/login，返回完整的 token pair 供前端自动续期（local 认证模式）。
    """
    user = await user_use_case.authenticate(login_data.email, login_data.password)
    token_pair = await user_use_case.create_token(user)

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    user_use_case: Annotated[UserUseCase, Depends(get_user_use_case)],
) -> TokenResponse:
    """使用 refresh_token 换取新的 token pair

    当 access_token 过期但 refresh_token 仍有效时，
    前端可调用此端点静默续期，无需用户重新登录。
    """

    token_pair = await user_use_case.refresh_token(data.refresh_token)

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )
