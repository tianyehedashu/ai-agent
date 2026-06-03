"""
Identity Presentation Schemas - 身份认证表示层模式

包含用户认证相关的所有请求响应模式
"""

from datetime import datetime
from typing import Self
import uuid

from fastapi_users.schemas import BaseUser, BaseUserCreate
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from domains.identity.domain.rbac import Role
from libs.api.pagination import PaginatedListResponse

# =============================================================================
# 用户读取模式（FastAPI Users 兼容）
# =============================================================================


class UserRead(BaseUser[uuid.UUID]):
    """用户读取模式（用于 FastAPI Users）"""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
    avatar_url: str | None = None
    vendor_creator_id: int | None = None


# =============================================================================
# 用户请求模式
# =============================================================================


class UserCreate(BaseUserCreate):
    """用户注册请求（继承 BaseUserCreate 以兼容 fastapi-users 注册路由）"""

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
    vendor_creator_id: int | None = Field(default=None, description="厂商系统操作用户 ID")


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
    """当前登录用户（依赖注入用，表示已认证用户）。"""

    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    role: str = "user"  # 用户角色：admin, user, viewer
    vendor_creator_id: int | None = None  # 厂商系统操作用户 ID

    @property
    def is_admin(self) -> bool:
        """是否是管理员"""
        return self.role == "admin"

    @property
    def is_superuser(self) -> bool:
        """是否是超级用户（与 is_admin 同义，兼容 FastAPI Users）"""
        return self.is_admin


class RefreshTokenRequest(BaseModel):
    """Refresh Token 请求"""

    model_config = ConfigDict(strict=True)

    refresh_token: str = Field(..., description="刷新令牌")


# =============================================================================
# 平台用户管理（Admin API）
# =============================================================================


class PlatformUserSummaryResponse(BaseModel):
    """平台用户摘要响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str | None = None
    role: str
    is_active: bool
    is_verified: bool
    status: str
    created_at: datetime
    vendor_creator_id: int | None = None
    avatar_url: str | None = None


class PlatformUserListResponse(PaginatedListResponse[PlatformUserSummaryResponse]):
    """平台用户分页列表响应。"""


class AdminUpdatePlatformUserBody(BaseModel):
    """平台管理员更新用户请求。"""

    model_config = ConfigDict(strict=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    vendor_creator_id: int | None = Field(default=None)
    is_active: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if (
            self.name is None
            and self.avatar_url is None
            and "vendor_creator_id" not in self.model_fields_set
            and self.is_active is None
        ):
            raise ValueError("At least one field must be provided")
        return self


class SetPlatformRoleBody(BaseModel):
    """设置平台角色请求。"""

    model_config = ConfigDict(strict=True)

    role: str = Field(
        ...,
        description="平台角色：admin、user、viewer",
        pattern=f"^({'|'.join([Role.ADMIN.value, Role.USER.value, Role.VIEWER.value])})$",
    )


__all__ = [
    "AdminUpdatePlatformUserBody",
    "CurrentUser",
    "PasswordChange",
    "PlatformUserListResponse",
    "PlatformUserSummaryResponse",
    "RefreshTokenRequest",
    "SetPlatformRoleBody",
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserRead",
    "UserResponse",
    "UserUpdate",
]
