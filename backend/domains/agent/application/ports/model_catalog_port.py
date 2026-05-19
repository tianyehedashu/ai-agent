"""Backward-compatible re-export — canonical definition is in gateway.application.ports."""

from domains.gateway.application.model_catalog_port import (
    ModelCapabilitySnapshot,
    ModelCatalogPort,
    RegisteredModelResolution,
)

__all__ = ["ModelCapabilitySnapshot", "ModelCatalogPort", "RegisteredModelResolution"]
