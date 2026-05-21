"""IAM 跨域抽象：租户作用域、默认租户供给、成员关系端口、请求级安全上下文。"""

from libs.iam.data_scope_policy import (
    DataAction,
    DataResource,
    enforce_data_scope,
    require_permission_context,
    resolve_team_ids_for_context,
)
from libs.iam.external_idp import (
    ExternalIdpClaimsView,
    external_idp_configured,
    parse_external_idp_claims,
)
from libs.iam.federation import FederatedIdentityAdapterPort, federation_is_active
from libs.iam.permission_context import (
    PermissionContext,
    clear_permission_context,
    ensure_tenant_in_team_ids,
    get_permission_context,
    merge_team_into_permission_context,
    set_permission_context,
)
from libs.iam.tenancy import (
    DefaultTenantProvisionerPort,
    MembershipPort,
    ScopeContext,
    TenantId,
)

__all__ = [
    "DataAction",
    "DataResource",
    "DefaultTenantProvisionerPort",
    "ExternalIdpClaimsView",
    "FederatedIdentityAdapterPort",
    "MembershipPort",
    "PermissionContext",
    "ScopeContext",
    "TenantId",
    "clear_permission_context",
    "enforce_data_scope",
    "ensure_tenant_in_team_ids",
    "get_permission_context",
    "merge_team_into_permission_context",
    "require_permission_context",
    "resolve_team_ids_for_context",
    "set_permission_context",
    "external_idp_configured",
    "federation_is_active",
    "parse_external_idp_claims",
]
