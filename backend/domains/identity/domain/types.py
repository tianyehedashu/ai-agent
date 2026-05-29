"""
Identity Domain Types - 身份域类型定义

包含身份认证相关的核心类型：
- Principal: 已认证身份主体
"""

from __future__ import annotations

from dataclasses import dataclass

# ============================================================================
# Principal（身份主体）
# ============================================================================


@dataclass(frozen=True, slots=True)
class Principal:
    """已认证身份主体（本地 JWT 或 giikin SSO 网关注入）。"""

    id: str
    email: str
    name: str
    role: str = "user"  # 用户角色：admin, user, viewer
    vendor_creator_id: int | None = None  # 厂商系统操作用户 ID

    def get_user_id(self) -> str:
        """获取注册用户 ID（用于数据库查询）"""
        return self.id
