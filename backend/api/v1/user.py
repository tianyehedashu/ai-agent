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


from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from api.deps import get_current_user, get_user_service, require_auth
from services.user import TokenPair, UserService

router = APIRouter()


# ============================================================================
# 请求/响应模型
# ============================================================================


class RegisterRequest(BaseModel):
    """注册请求"""

    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    """登录请求"""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """刷新 Token 请求"""

    refresh_token: str


class UpdateUserRequest(BaseModel):
    """更新用户请求"""

    name: str | None = None
    avatar: str | None = None


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""

    current_password: str
    new_password: str


class UserResponse(BaseModel):
    """用户响应"""

    id: str
    email: str
    name: str
    avatar: str | None
    role: str
    created_at: str


class AuthResponse(BaseModel):
    """认证响应"""

    user: UserResponse
    token: TokenPair


# ============================================================================
# 认证 API
# ============================================================================


@router.post("/register", response_model=AuthResponse)
async def register(
    request: RegisterRequest,
    user_service: UserService = Depends(get_user_service),
) -> AuthResponse:
    """用户注册"""
    # 检查邮箱是否已存在
    existing = await user_service.get_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
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
            avatar=user.avatar,
            role=user.role,
            created_at=user.created_at.isoformat(),
        ),
        token=token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    user_service: UserService = Depends(get_user_service),
) -> AuthResponse:
    """用户登录"""
    user = await user_service.authenticate(
        email=request.email,
        password=request.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # 检查用户状态
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # 生成 Token
    token = await user_service.create_token(user)

    return AuthResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            avatar=user.avatar,
            role=user.role,
            created_at=user.created_at.isoformat(),
        ),
        token=token,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    request: RefreshRequest,
    user_service: UserService = Depends(get_user_service),
) -> TokenPair:
    """刷新 Token"""
    try:
        return await user_service.refresh_token(request.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from e


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(require_auth),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """获取当前用户"""
    user = await user_service.get_by_id(current_user["id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar=user.avatar,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    request: UpdateUserRequest,
    current_user: dict = Depends(require_auth),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """更新当前用户"""
    update_data = {}
    if request.name is not None:
        update_data["name"] = request.name
    if request.avatar is not None:
        update_data["avatar"] = request.avatar

    user = await user_service.update(current_user["id"], update_data)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar=user.avatar,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(require_auth),
    user_service: UserService = Depends(get_user_service),
) -> dict[str, str]:
    """修改密码"""
    # 验证当前密码
    is_valid = await user_service.verify_password(
        current_user["id"],
        request.current_password,
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # 修改密码
    await user_service.change_password(current_user["id"], request.new_password)

    return {"message": "Password changed successfully"}


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """
    用户登出

    注意: JWT 是无状态的，登出通常在客户端清除 Token
    如需服务端黑名单，可以使用 Redis 存储失效的 Token
    """
    return {"message": "Logged out successfully"}
