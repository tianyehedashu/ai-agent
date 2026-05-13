"""IAM 跨域抽象：租户作用域、默认租户供给、成员关系端口。"""

from libs.iam.external_idp import (
    ExternalIdpClaimsView,
    external_idp_configured,
    parse_external_idp_claims,
)
from libs.iam.federation import FederatedIdentityAdapterPort, federation_is_active
from libs.iam.tenancy import (
    DefaultTenantProvisionerPort,
    MembershipPort,
    ScopeContext,
    TenantId,
)

__all__ = [
    "DefaultTenantProvisionerPort",
    "ExternalIdpClaimsView",
    "FederatedIdentityAdapterPort",
    "MembershipPort",
    "ScopeContext",
    "TenantId",
    "external_idp_configured",
    "federation_is_active",
    "parse_external_idp_claims",
]
