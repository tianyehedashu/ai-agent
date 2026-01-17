"""
环境变量解析器

解析配置中的环境变量引用
"""

import os
import re
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)


class EnvVarResolver:
    """
    环境变量解析器

    支持格式：
    - ${VAR} - 必须存在的环境变量
    - ${VAR:default} - 带默认值的环境变量
    """

    # 匹配 ${VAR} 或 ${VAR:default}
    ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")

    def resolve(self, data: Any) -> Any:
        """
        递归解析数据中的环境变量引用

        Args:
            data: 要解析的数据（可以是字典、列表、字符串等）

        Returns:
            解析后的数据
        """
        if isinstance(data, str):
            return self._resolve_string(data)
        elif isinstance(data, dict):
            return {k: self.resolve(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.resolve(item) for item in data]
        return data

    def _resolve_string(self, value: str) -> str:
        """解析字符串中的环境变量"""

        def replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            default = match.group(2)
            env_value = os.environ.get(var_name, default)

            if env_value is None:
                logger.warning(
                    "Environment variable '%s' not found and no default provided",
                    var_name,
                )
                return match.group(0)  # 保留原样

            return env_value

        return self.ENV_PATTERN.sub(replace, value)

    def has_unresolved(self, data: Any) -> list[str]:
        """
        检查数据中是否有未解析的环境变量

        Args:
            data: 要检查的数据

        Returns:
            未解析的环境变量列表
        """
        unresolved: list[str] = []
        self._find_unresolved(data, unresolved)
        return unresolved

    def _find_unresolved(self, data: Any, unresolved: list[str]) -> None:
        """递归查找未解析的环境变量"""
        if isinstance(data, str):
            matches = self.ENV_PATTERN.findall(data)
            for var_name, default in matches:
                if default is None and os.environ.get(var_name) is None:
                    unresolved.append(var_name)
        elif isinstance(data, dict):
            for v in data.values():
                self._find_unresolved(v, unresolved)
        elif isinstance(data, list):
            for item in data:
                self._find_unresolved(item, unresolved)
