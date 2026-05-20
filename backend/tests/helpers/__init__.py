"""跨测试目录共享辅助（非 pytest conftest）。"""

from tests.helpers.bridge_identity import patch_bridge_identity

__all__ = ["patch_bridge_identity"]
