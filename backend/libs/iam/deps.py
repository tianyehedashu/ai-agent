"""IAM 相关 FastAPI 依赖（composition root 绑定实现）。"""

from __future__ import annotations

from libs.iam.tenancy import DefaultTenantProvisionerPort


def get_default_tenant_provisioner() -> DefaultTenantProvisionerPort:
    """默认租户供给：当前绑定 domains.tenancy.application.TeamService 实现。"""
    from domains.gateway.infrastructure.iam.default_tenant_provisioner import (
        GatewayDefaultTenantProvisioner,
    )

    return GatewayDefaultTenantProvisioner()


__all__ = ["get_default_tenant_provisioner"]
