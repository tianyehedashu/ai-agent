"""
Code Fixer - 代码自动修复器

使用 LLM 修复代码问题:
- 语法错误
- 类型错误
- Lint 问题
- 架构规范问题
"""

from typing import Any

from shared.infrastructure.llm.gateway import LLMGateway
from domains.studio.infrastructure.quality.validator import CodeValidator, ValidationResult
from utils.logging import get_logger

logger = get_logger(__name__)


FIX_PROMPT = """请修复以下 Python 代码中的问题。

代码:
```python
{code}
```

发现的问题:
{issues}

请修复所有问题并返回完整的修复后代码。只返回代码，不要包含任何解释。
代码必须用 ```python 和 ``` 包裹。
"""


class CodeFixer:
    """
    代码自动修复器

    使用 LLM 修复代码问题，支持多轮修复
    """

    def __init__(
        self,
        llm: LLMGateway,
        validator: CodeValidator | None = None,
        max_attempts: int = 3,
    ) -> None:
        """
        初始化代码修复器

        Args:
            llm: LLM 网关（必须提供，通过依赖注入）
            validator: 代码验证器
            max_attempts: 最大修复尝试次数
        """
        self.llm = llm
        self.validator = validator or CodeValidator()
        self.max_attempts = max_attempts

    async def fix(
        self,
        code: str,
        validation_result: ValidationResult | None = None,
    ) -> tuple[str, bool]:
        """
        修复代码

        Args:
            code: 原始代码
            validation_result: 验证结果 (可选，不提供则自动验证)

        Returns:
            (修复后的代码, 是否修复成功)
        """
        # 如果没有提供验证结果，先验证
        if validation_result is None:
            validation_result = await self.validator.validate(code)

        # 如果没有问题，直接返回
        if validation_result.is_valid:
            return code, True

        current_code = code
        attempt = 0

        while attempt < self.max_attempts:
            attempt += 1
            logger.info("Fix attempt %d/%d", attempt, self.max_attempts)

            # 构建问题描述
            issues_text = self._format_issues(validation_result)

            # 调用 LLM 修复
            prompt = FIX_PROMPT.format(
                code=current_code,
                issues=issues_text,
            )

            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=None,  # 使用 LLMGateway 的默认模型
                    temperature=0.3,
                )

                # 提取代码
                fixed_code = self._extract_code(response.content or "")

                if not fixed_code:
                    logger.warning("Failed to extract code from LLM response")
                    continue

                # 验证修复后的代码
                new_result = await self.validator.validate(fixed_code)

                if new_result.is_valid:
                    logger.info("Code fixed successfully")
                    return fixed_code, True

                # 如果错误减少，继续尝试
                if new_result.errors < validation_result.errors:
                    current_code = fixed_code
                    validation_result = new_result
                    logger.info(
                        "Errors reduced: %d -> %d",
                        validation_result.errors,
                        new_result.errors,
                    )
                else:
                    logger.warning("Fix attempt did not reduce errors")

            except Exception as e:
                logger.error("Fix attempt failed: %s", e)

        # 返回最后的代码（可能部分修复）
        return current_code, validation_result.is_valid

    async def fix_single_issue(
        self,
        code: str,
        issue: dict[str, Any],
    ) -> str:
        """
        修复单个问题

        Args:
            code: 原始代码
            issue: 问题信息

        Returns:
            修复后的代码
        """
        prompt = f"""请修复以下 Python 代码中的问题。

代码:
```python
{code}
```

问题:
- 行 {issue.get("line", 0) + 1}: {issue.get("message", "")} [{issue.get("code", "")}]

请只修复这个问题，保持其他代码不变。只返回完整的修复后代码。
代码必须用 ```python 和 ``` 包裹。
"""

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=None,  # 使用 LLMGateway 的默认模型
                temperature=0.3,
            )

            fixed_code = self._extract_code(response.content or "")
            return fixed_code if fixed_code else code

        except Exception as e:
            logger.error("Single fix failed: %s", e)
            return code

    def _format_issues(self, result: ValidationResult) -> str:
        """格式化问题列表"""
        lines = []
        for issue in result.issues:
            lines.append(
                f"- 行 {issue.line + 1}: [{issue.code}] {issue.message} (来源: {issue.source})"
            )
        return "\n".join(lines)

    def _extract_code(self, response: str) -> str | None:
        """从 LLM 响应中提取代码"""
        # 尝试提取 ```python ... ``` 块
        if "```python" in response:
            parts = response.split("```python")
            if len(parts) > 1:
                code_part = parts[1].split("```")[0]
                return code_part.strip()

        # 尝试提取 ``` ... ``` 块
        if "```" in response:
            parts = response.split("```")
            if len(parts) > 1:
                code_part = parts[1]
                # 跳过可能的语言标识
                lines = code_part.split("\n")
                if lines and lines[0].strip() in ("python", "py", ""):
                    code_part = "\n".join(lines[1:])
                return code_part.strip()

        return None
