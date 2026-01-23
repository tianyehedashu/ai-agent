"""
Shared Presentation Schemas - 跨领域共享模
仅包含真正跨领域共享的模式，领域特定的模式应放在各自presentation 层
用户相关的模式已移动到：domains/identity/presentation/schemas.py
"""

from pydantic import BaseModel, ConfigDict


class CurrentUser(BaseModel):
    """当前登录用户

    用于依赖注入，表示已认证的用户信息    支持注册用户和匿名用户
    注意：这是一个跨领域共享的模式，因为多个领域API 都需要获取当前用户    """

    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    is_anonymous: bool = False


__all__ = ["CurrentUser"]
