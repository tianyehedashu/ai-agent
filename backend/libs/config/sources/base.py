"""
配置源抽象基类

定义配置加载的统一接口，支持多种配置来源：
- TOML 文件
- 数据库
- 远程配置中心 (Consul/Nacos/Apollo)
"""

from abc import ABC, abstractmethod
from typing import Any


class ConfigSource(ABC):
    """
    配置源抽象基类

    所有配置来源必须实现此接口，确保可插拔性。
    """

    @abstractmethod
    def load(self, identifier: str) -> dict[str, Any] | None:
        """
        加载配置

        Args:
            identifier: 配置标识符 (如 agent_id 或 template_name)

        Returns:
            配置字典，如果不存在返回 None
        """
        pass

    @abstractmethod
    def exists(self, identifier: str) -> bool:
        """
        检查配置是否存在

        Args:
            identifier: 配置标识符

        Returns:
            是否存在
        """
        pass

    @abstractmethod
    def list_available(self) -> list[str]:
        """
        列出所有可用配置

        Returns:
            配置标识符列表
        """
        pass

    def save(self, identifier: str, data: dict[str, Any]) -> bool:
        """
        保存配置 (可选实现)

        Args:
            identifier: 配置标识符
            data: 配置数据

        Returns:
            是否保存成功
        """
        raise NotImplementedError("This source does not support saving")

    def delete(self, identifier: str) -> bool:
        """
        删除配置 (可选实现)

        Args:
            identifier: 配置标识符

        Returns:
            是否删除成功
        """
        raise NotImplementedError("This source does not support deletion")
