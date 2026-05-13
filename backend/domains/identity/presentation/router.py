"""
Identity API - 用户认证接口
"""

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application import UserUseCase
from domains.identity.application.principal_service import ANONYMOUS_USER_COOKIE
from domains.identity.application.session_migration_service import migrate_anonymous_data_on_auth
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
from libs.db.database import get_db
from libs.exceptions import AuthenticationError
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
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    获取当前用户信息（支持匿名用户）

    在开发模式下支持匿名用户，生产模式下需要真实认证
    """
    logger.info(
        "GET /api/v1/auth/me - user_id=%s, is_anonymous=%s",
        current_user.id,
        current_user.is_anonymous,
    )
    return current_user


@router.put("/me", response_model=UserRead)
async def update_me(
    data: UserUpdate,
    user=Depends(current_active_user),
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    """更新当前用户"""
    user_service = UserUseCase(session)
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
    user=Depends(current_active_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """修改密码"""
    user_service = UserUseCase(session)
    await user_service.change_password(
        user_id=str(user.id),
        old_password=request.old_password,
        new_password=request.new_password,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    """
    退出登录
    清除匿名用户cookie，允许用户重新登录或创建新的匿名会话
    """
    response.delete_cookie(
        key=ANONYMOUS_USER_COOKIE,
        path="/",
        samesite="lax",
    )


# =============================================================================
# Token 端点（增强版登录 + Refresh）
# =============================================================================


@router.post("/token", response_model=TokenResponse)
async def login_for_token_pair(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """登录并获取 Token 对（access_token + refresh_token）

    替代 /jwt/login，返回完整的 token pair 供前端自动续期。
    同时触发匿名数据迁移（将当前浏览器的匿名会话/任务关联到登录账号）。
    """
    user_use_case = UserUseCase(db)

    try:
        user = await user_use_case.authenticate(login_data.email, login_data.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc

    # 创建 token pair
    token_pair = await user_use_case.create_token(user)

    # 迁移匿名数据（与 on_after_login 逻辑一致）
    anonymous_user_id = request.cookies.get(ANONYMOUS_USER_COOKIE)
    if anonymous_user_id:
        result = await migrate_anonymous_data_on_auth(db, user.id, anonymous_user_id)
        if result.total > 0:
            logger.info(
                "Post-login migration for user %s: %d sessions, %d video_tasks",
                user.id,
                result.sessions,
                result.video_tasks,
            )

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """使用 refresh_token 换取新的 token pair

    当 access_token 过期但 refresh_token 仍有效时，
    前端可调用此端点静默续期，无需用户重新登录。
    """
    user_use_case = UserUseCase(db)

    try:
        token_pair = await user_use_case.refresh_token(data.refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )
