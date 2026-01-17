"""
Memory Extractor - 记忆提取器

专门负责从对话中提取重要信息，存储使用 LongTermMemoryStore
"""

import json
from typing import Any

from core.llm.gateway import LLMGateway
from core.memory.langgraph_store import LongTermMemoryStore
from utils.logging import get_logger

logger = get_logger(__name__)


EXTRACTION_PROMPT = """从以下对话中提取重要的、值得长期记住的信息。

对话内容:
{conversation}

请提取以下类型的信息:
1. 用户偏好 (preferences)
2. 重要事实 (facts)
3. 关键决策 (decisions)
4. 待办事项 (todos)

对于每条记忆，请给出:
- content: 记忆内容
- type: 记忆类型 (preference/fact/decision/todo)
- importance: 重要性评分 (1-10)

以 JSON 数组格式返回，如果没有值得记住的信息，返回空数组 []。"""


class MemoryExtractor:
    """
    记忆提取器

    专门负责从对话中提取重要信息
    存储由 LongTermMemoryStore 负责
    """

    def __init__(self, llm_gateway: LLMGateway) -> None:
        """
        初始化记忆提取器

        Args:
            llm_gateway: LLM 网关（用于提取记忆）
        """
        self.llm_gateway = llm_gateway

    async def extract(
        self,
        conversation: list[dict[str, Any]],
        model: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        从对话中提取记忆

        Args:
            conversation: 对话历史
            model: 使用的模型（可选，默认使用 LLM Gateway 的默认模型）

        Returns:
            提取的记忆列表，包含 content, type, importance
        """
        # 格式化对话
        conv_text = self._format_conversation(conversation)

        # 调用 LLM 提取记忆
        prompt = EXTRACTION_PROMPT.format(conversation=conv_text)

        try:
            response = await self.llm_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                model=model,  # 如果为 None，LLM Gateway 会使用默认模型
                temperature=0.3,
            )

            # 解析响应
            content = response.content or "[]"
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            extracted = json.loads(content.strip())

            if not isinstance(extracted, list):
                return []

            # 验证和清理提取的记忆
            memories = []
            for item in extracted:
                if not isinstance(item, dict):
                    continue

                # 验证必需字段
                if not item.get("content") or not item.get("type"):
                    continue

                memories.append(
                    {
                        "content": item.get("content", ""),
                        "type": item.get("type", "fact"),
                        "importance": float(item.get("importance", 5)),
                    }
                )

            logger.info("Extracted %d memories from conversation", len(memories))
            return memories

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Memory extraction error: %s", e, exc_info=True)
            return []

    async def extract_and_store(
        self,
        memory_store: LongTermMemoryStore,
        session_id: str,
        conversation: list[dict[str, Any]],
        user_id: str | None = None,
        model: str | None = None,
    ) -> list[str]:
        """
        提取记忆并存储到 LongTermMemoryStore

        记忆按 session_id 隔离，实现"会话内长程记忆"。

        Args:
            memory_store: 长期记忆存储
            session_id: 会话 ID（记忆按会话隔离）
            conversation: 对话历史
            user_id: 用户 ID（可选，用于审计）
            model: 使用的模型（可选）

        Returns:
            存储的记忆 ID 列表
        """
        # 提取记忆
        extracted = await self.extract(conversation, model)

        # 存储到 LongTermMemoryStore
        memory_ids = []
        for memory in extracted:
            memory_id = await memory_store.put(
                session_id=session_id,  # 记忆按会话隔离
                memory_type=memory["type"],
                content=memory["content"],
                importance=memory["importance"],
                metadata={
                    "user_id": user_id,
                    "extracted": True,
                },
            )
            memory_ids.append(memory_id)

        logger.info("Stored %d memories to LongTermMemoryStore", len(memory_ids))
        return memory_ids

    def _format_conversation(self, conversation: list[dict[str, Any]]) -> str:
        """格式化对话"""
        lines = []
        for msg in conversation:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
