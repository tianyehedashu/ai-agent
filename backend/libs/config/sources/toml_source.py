"""
TOML 文件配置源

从本地 TOML 文件加载配置
"""

from pathlib import Path
import tomllib
from typing import Any

import tomli_w

from utils.logging import get_logger

from .base import ConfigSource

logger = get_logger(__name__)


class TomlConfigSource(ConfigSource):
    """
    TOML 文件配置源

    从指定目录加载 TOML 配置文件
    """

    def __init__(self, base_dir: Path | str, suffix: str = ".toml") -> None:
        """
        初始化 TOML 配置源

        Args:
            base_dir: 配置文件所在目录
            suffix: 文件后缀，默认 .toml
        """
        self.base_dir = Path(base_dir)
        self.suffix = suffix

    def load(self, identifier: str) -> dict[str, Any] | None:
        """从 TOML 文件加载配置"""
        path = self._get_path(identifier)
        if not path.exists():
            return None

        try:
            with path.open("rb") as f:
                return tomllib.load(f)
        except Exception as e:
            logger.error("Failed to load TOML config from %s: %s", path, e)
            return None

    def exists(self, identifier: str) -> bool:
        """检查 TOML 文件是否存在"""
        return self._get_path(identifier).exists()

    def list_available(self) -> list[str]:
        """列出目录下所有 TOML 配置"""
        if not self.base_dir.exists():
            return []

        configs = []
        for path in self.base_dir.glob(f"*{self.suffix}"):
            # 跳过以 _ 开头的文件（如 _base.toml）
            if not path.stem.startswith("_"):
                configs.append(path.stem)

        return configs

    def save(self, identifier: str, data: dict[str, Any]) -> bool:
        """保存配置到 TOML 文件"""
        path = self._get_path(identifier)

        try:
            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)

            with path.open("wb") as f:
                tomli_w.dump(data, f)
            return True
        except Exception as e:
            logger.error("Failed to save TOML config to %s: %s", path, e)
            return False

    def delete(self, identifier: str) -> bool:
        """删除 TOML 配置文件"""
        path = self._get_path(identifier)

        if not path.exists():
            return True  # 不存在视为删除成功

        try:
            path.unlink()
            return True
        except Exception as e:
            logger.error("Failed to delete TOML config %s: %s", path, e)
            return False

    def _get_path(self, identifier: str) -> Path:
        """获取配置文件路径"""
        return self.base_dir / f"{identifier}{self.suffix}"


class AgentTomlSource(TomlConfigSource):
    """
    Agent TOML 配置源

    从 agents/{agent_id}/agent.toml 加载配置
    """

    def __init__(self, agents_dir: Path | str) -> None:
        """
        初始化 Agent 配置源

        Args:
            agents_dir: agents 目录路径
        """
        super().__init__(agents_dir)

    def _get_path(self, identifier: str) -> Path:
        """Agent 配置路径: agents/{agent_id}/agent.toml"""
        return self.base_dir / identifier / "agent.toml"

    def list_available(self) -> list[str]:
        """列出所有有配置的 Agent"""
        if not self.base_dir.exists():
            return []

        agents = []
        for agent_dir in self.base_dir.iterdir():
            if agent_dir.is_dir():
                config_path = agent_dir / "agent.toml"
                if config_path.exists():
                    agents.append(agent_dir.name)

        return agents
