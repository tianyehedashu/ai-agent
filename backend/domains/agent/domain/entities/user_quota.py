"""用户配额值对象 - 封装业务规则

定义不同用户类型（匿名用户/注册用户）的资源限制规则。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UserQuota:
    """用户配额值对象

    封装不同用户类型的业务限制规则。
    作为值对象，保证不可变性。

    Attributes:
        max_sessions: 最大会话数
        max_sandboxes: 最大沙箱数
        sandbox_idle_timeout: 沙箱空闲超时（秒）
        sandbox_max_duration: 沙箱最大时长（秒）
    """

    max_sessions: int
    max_sandboxes: int
    sandbox_idle_timeout: int  # 秒
    sandbox_max_duration: int  # 秒

    @classmethod
    def for_anonymous(cls) -> "UserQuota":
        """匿名用户配额（业务规则）

        匿名用户资源受限：
        - 只能有 1 个会话
        - 只能有 1 个沙箱
        - 30 分钟空闲超时
        - 2 小时最大时长
        """
        return cls(
            max_sessions=1,
            max_sandboxes=1,
            sandbox_idle_timeout=1800,  # 30 分钟
            sandbox_max_duration=7200,  # 2 小时
        )

    @classmethod
    def for_registered(cls) -> "UserQuota":
        """注册用户配额（业务规则）

        注册用户资源更宽松：
        - 最多 10 个会话
        - 最多 5 个沙箱
        - 2 小时空闲超时
        - 8 小时最大时长
        """
        return cls(
            max_sessions=10,
            max_sandboxes=5,
            sandbox_idle_timeout=7200,  # 2 小时
            sandbox_max_duration=28800,  # 8 小时
        )

    @classmethod
    def for_user(cls, is_anonymous: bool) -> "UserQuota":
        """根据用户类型获取配额

        Args:
            is_anonymous: 是否为匿名用户

        Returns:
            对应用户类型的配额
        """
        return cls.for_anonymous() if is_anonymous else cls.for_registered()
