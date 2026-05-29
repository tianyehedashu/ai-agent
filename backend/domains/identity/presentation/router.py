"""
Identity API - 用户认证接口
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from pydantic import BaseModel, Field

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
