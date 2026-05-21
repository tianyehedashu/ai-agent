"""IAM 相关 FastAPI 依赖（composition root 绑定实现）。"""

from __future__ import annotations

from libs.iam.tenancy import DefaultTenantProvisionerPort


def get_default_tenant_provisioner() -> DefaultTenantProvisionerPort:
    """默认租户供给：绑定 tenancy 域 ``TenancyDefaultTenantProvisioner``。"""
    from domains.tenancy.application.default_tenant_provisioner import (
        TenancyDefaultTenantProvisioner,
    )

    return TenancyDefaultTenantProvisioner()


__all__ = ["get_default_tenant_provisioner"]
