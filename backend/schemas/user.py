"""
User Schemas - 用户相关 Schema

提供用户认证、请求/响应的数据结构。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CurrentUser(BaseModel):
    """当前登录用户

    用于依赖注入，表示已认证的用户信息。
    """

    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    is_anonymous: bool = False


class UserCreate(BaseModel):
    """用户注册请求"""

    model_config = ConfigDict(strict=True)

    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, max_length=100, description="密码")
    name: str = Field(..., min_length=1, max_length=100, description="用户名")


class UserLogin(BaseModel):
    """用户登录请求"""

    model_config = ConfigDict(strict=True)

    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """用户更新请求"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)


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


class PasswordChange(BaseModel):
    """密码修改请求"""

    model_config = ConfigDict(strict=True)

    old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=100)
