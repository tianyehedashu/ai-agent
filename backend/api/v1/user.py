"""
User API - 用户认证 API

实现:
- POST /auth/register: 用户注册
- POST /auth/login: 用户登录
- POST /auth/refresh: 刷新 Token
- GET /auth/me: 获取当前用户
- PUT /auth/me: 更新当前用户
- POST /auth/change-password: 修改密码
"""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from api.deps import AuthUser, RequiredAuthUser, get_user_service
from exceptions import ConflictError
from schemas.user import TokenResponse
from services.user import UserService

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class RegisterRequest(BaseModel):
    """注册请求"""

    model_config = ConfigDict(strict=True)

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)


class LoginRequest(BaseModel):
    """登录请求"""

    model_config = ConfigDict(strict=True)

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """刷新 Token 请求"""

    refresh_token: str


class UpdateUserRequest(BaseModel):
    """更新用户请求"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""

    model_config = ConfigDict(strict=True)

    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=100)


class UserResponse(BaseModel):
    """用户响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str | None
    avatar_url: str | None
    status: str
    created_at: datetime


class AuthResponse(BaseModel):
    """认证响应"""

    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# =============================================================================
# 认证 API
# =============================================================================


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    user_service: UserService = Depends(get_user_service),
) -> AuthResponse:
    """用户注册"""
    # 检查邮箱是否已存在
    existing = await user_service.get_by_email(request.email)
    if existing:
        raise ConflictError(
            message="Email already registered",
            resource="User",
        )

    # 创建用户
    user = await user_service.create(
        email=request.email,
        password=request.password,
        name=request.name,
    )

    # 生成 Token
    token = await user_service.create_token(user)

    return AuthResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            status=user.status,
            created_at=user.created_at,
        ),
        access_token=token.access_token,
        expires_in=token.expires_in,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    user_service: UserService = Depends(get_user_service),
) -> AuthResponse:
    """用户登录"""
    # authenticate 会在失败时抛出 AuthenticationError
    user = await user_service.authenticate(
        email=request.email,
        password=request.password,
    )

    # 生成 Token
    token = await user_service.create_token(user)

    return AuthResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            status=user.status,
            created_at=user.created_at,
        ),
        access_token=token.access_token,
        expires_in=token.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    user_service: UserService = Depends(get_user_service),
) -> TokenResponse:
    """刷新 Token"""
    # refresh_token 会在失败时抛出 TokenError
    token = await user_service.refresh_token(request.refresh_token)

    return TokenResponse(
        access_token=token.access_token,
        expires_in=token.expires_in,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: RequiredAuthUser,
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """获取当前用户"""
    # get_by_id_or_raise 会在用户不存在时抛出 NotFoundError
    user = await user_service.get_by_id_or_raise(current_user.id)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        status=user.status,
        created_at=user.created_at,
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    request: UpdateUserRequest,
    current_user: RequiredAuthUser,
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """更新当前用户"""
    user = await user_service.update(
        user_id=current_user.id,
        name=request.name,
        avatar_url=request.avatar_url,
    )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        status=user.status,
        created_at=user.created_at,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: ChangePasswordRequest,
    current_user: RequiredAuthUser,
    user_service: UserService = Depends(get_user_service),
) -> None:
    """修改密码"""
    # change_password 会在验证失败时抛出 AuthenticationError
    await user_service.change_password(
        user_id=current_user.id,
        old_password=request.current_password,
        new_password=request.new_password,
    )


@router.post("/logout")
async def logout(
    current_user: AuthUser,
) -> dict[str, str]:
    """
    用户登出

    注意: JWT 是无状态的，登出通常在客户端清除 Token
    如需服务端黑名单，可以使用 Redis 存储失效的 Token
    """
    return {"message": "Logged out successfully"}
