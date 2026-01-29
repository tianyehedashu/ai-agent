"""
Identity API - 用户认证接口
"""

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application import UserUseCase
from domains.identity.application.principal_service import ANONYMOUS_USER_COOKIE
from domains.identity.infrastructure.authentication import (
    auth_backend,
    current_active_user,
    fastapi_users,
)
from domains.identity.presentation.deps import get_current_user
from domains.identity.presentation.schemas import CurrentUser, UserCreate, UserRead, UserUpdate
from libs.api.deps import get_db

router = APIRouter()

# FastAPI Users routers
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
    from utils.logging import get_logger

    logger = get_logger(__name__)
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
    updated = await user_service.update(
        user_id=str(user.id),
        name=data.name,
        avatar_url=data.avatar_url,
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
    退出登
    清除匿名用户cookie，允许用户重新登录或创建新的匿名会话"""
    # 清除anonymous_user_id cookie
    response.delete_cookie(
        key=ANONYMOUS_USER_COOKIE,
        path="/",
        samesite="lax",
    )
