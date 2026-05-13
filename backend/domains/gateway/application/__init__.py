"""Gateway Application Layer - 应用层（用例编排）

约定（避免过度拆分）：
- **UseCase**：按端到端场景（如 `ProxyUseCase`、`GatewayAccessUseCase`），可含多条读与少量写。
- **管理面读写服务**：CRUD 密集区使用 `GatewayManagementReadService` / `GatewayManagementWriteService`（`application/management/`，与 CQRS 读/写侧一一对应），与 UseCase 互补而非替代全部应用层。
- **跨域内部桥接**：端口与 DTO 在 `ports.py`（与 `domains.session.application.ports` 同构）；实现见 `internal_bridge.py`，工厂见 `gateway_proxy_factory.py`。
"""
