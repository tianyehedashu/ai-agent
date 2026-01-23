"""
Identity Presentation Schemas - 身份认证表示层模式

包含用户认证相关的所有请求响应模式
"""

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# =============================================================================
# 用户读取模式（FastAPI Users 兼容）
# =============================================================================


class UserRead(BaseModel):
    """用户读取模式（用于 FastAPI Users）"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_active: bool = True
    name: str | None = None
    avatar_url: str | None = None


# =============================================================================
# 用户请求模式
# =============================================================================


class UserCreate(BaseModel):
    """用户注册请求"""

    model_config = ConfigDict(strict=True)

    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, max_length=100, description="密码")
    name: str | None = Field(default=None, min_length=1, max_length=100, description="用户名")


class UserLogin(BaseModel):
    """用户登录请求"""

    model_config = ConfigDict(strict=True)

    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """用户更新请求"""

    email: str | None = None
    password: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)


class PasswordChange(BaseModel):
    """密码修改请求"""

    model_config = ConfigDict(strict=True)

    old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=100)


# =============================================================================
# 用户响应模式
# =============================================================================


class UserResponse(BaseModel):
    """用户响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str | None
    avatar_url: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Token 响应"""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


# =============================================================================
# 当前用户模式（依赖注入用）
# =============================================================================


class CurrentUser(BaseModel):
    """当前登录用户

    用于依赖注入，表示已认证的用户信息
    支持注册用户和匿名用户
    """

    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    is_anonymous: bool = False


__all__ = [
    "CurrentUser",
    "PasswordChange",
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserRead",
    "UserResponse",
    "UserUpdate",
]
