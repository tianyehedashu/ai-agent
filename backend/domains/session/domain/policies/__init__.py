"""Session 域策略。"""

from domains.session.domain.policies.session_access import (
    SessionTenantLike,
    is_session_in_personal_tenant,
)

__all__ = ["SessionTenantLike", "is_session_in_personal_tenant"]
