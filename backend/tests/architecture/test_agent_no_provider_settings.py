"""架构守门：Agent 域不得读取 settings 中的 provider API Key（与 litellm 守门分文件，计划 T7）。"""

from tests.architecture.test_agent_no_litellm_import import (
    test_agent_domain_has_no_settings_provider_api_key_access,
)

__all__ = ["test_agent_domain_has_no_settings_provider_api_key_access"]
