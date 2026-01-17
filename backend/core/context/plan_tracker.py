"""
Plan Tracker - 计划追踪器

基于 PAACE 论文实现计划感知的上下文管理：
1. 跟踪 Agent 的任务计划结构
2. 识别当前阶段和下一步任务
3. 判断哪些历史与未来任务相关

参考论文：
- PAACE: Plan-Aware Automated Agent Context Engineering (2025)
- FoldAct: Efficient and Stable Context Folding (2025)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
import re
from typing import Any

from core.types import Message, MessageRole
from utils.logging import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"  # 待执行
    IN_PROGRESS = "in_progress"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    BLOCKED = "blocked"  # 阻塞


class TaskType(Enum):
    """任务类型"""

    ANALYSIS = "analysis"  # 分析
    PLANNING = "planning"  # 规划
    IMPLEMENTATION = "implementation"  # 实现
    TESTING = "testing"  # 测试
    DEBUGGING = "debugging"  # 调试
    REVIEW = "review"  # 评审
    DOCUMENTATION = "documentation"  # 文档
    OTHER = "other"  # 其他


@dataclass
class PlanStep:
    """计划步骤"""

    id: str
    description: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)  # 依赖的步骤 ID
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    related_messages: list[int] = field(default_factory=list)  # 相关消息索引
    artifacts: list[str] = field(default_factory=list)  # 产出（如文件路径）
    notes: str = ""  # 备注


@dataclass
class TaskPlan:
    """任务计划"""

    goal: str  # 总目标
    steps: list[PlanStep] = field(default_factory=list)
    current_step_idx: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def current_step(self) -> PlanStep | None:
        """获取当前步骤"""
        if 0 <= self.current_step_idx < len(self.steps):
            return self.steps[self.current_step_idx]
        return None

    @property
    def completed_steps(self) -> list[PlanStep]:
        """获取已完成的步骤"""
        return [s for s in self.steps if s.status == TaskStatus.COMPLETED]

    @property
    def pending_steps(self) -> list[PlanStep]:
        """获取待执行的步骤"""
        return [s for s in self.steps if s.status == TaskStatus.PENDING]

    @property
    def progress(self) -> float:
        """计划进度 (0.0 - 1.0)"""
        if not self.steps:
            return 0.0
        completed = len(self.completed_steps)
        return completed / len(self.steps)


class PlanTracker:
    """
    计划追踪器

    负责：
    1. 从对话中提取和维护任务计划
    2. 跟踪当前执行阶段
    3. 判断消息与计划的相关性
    4. 在阶段切换时触发上下文压缩
    """

    def __init__(self) -> None:
        self._plan: TaskPlan | None = None
        self._phase_changed = False
        self._last_phase: str | None = None

    @property
    def plan(self) -> TaskPlan | None:
        """获取当前计划"""
        return self._plan

    @property
    def has_plan(self) -> bool:
        """是否有计划"""
        return self._plan is not None

    @property
    def phase_changed(self) -> bool:
        """
        阶段是否变更

        当阶段变更时，通常是触发上下文压缩的好时机。
        """
        return self._phase_changed

    def reset_phase_changed(self) -> None:
        """重置阶段变更标记"""
        self._phase_changed = False

    def set_plan(self, goal: str, steps: list[dict[str, Any]]) -> None:
        """
        设置计划

        Args:
            goal: 总目标
            steps: 步骤列表，每个步骤包含 description, type, dependencies
        """
        plan_steps = []
        for i, step in enumerate(steps):
            plan_steps.append(
                PlanStep(
                    id=f"step_{i}",
                    description=step.get("description", f"步骤 {i + 1}"),
                    task_type=TaskType(step.get("type", "other")),
                    dependencies=step.get("dependencies", []),
                )
            )

        self._plan = TaskPlan(goal=goal, steps=plan_steps)
        logger.info("Plan set: %s with %d steps", goal[:50], len(plan_steps))

    def extract_plan_from_messages(self, messages: list[Message]) -> bool:
        """
        从消息中自动提取计划

        尝试从对话中识别任务计划结构。

        Args:
            messages: 消息列表

        Returns:
            是否成功提取计划
        """
        for msg in messages:
            if msg.role != MessageRole.ASSISTANT or not msg.content:
                continue

            # 尝试提取计划
            plan = self._parse_plan_from_content(msg.content)
            if plan:
                self._plan = plan
                logger.info("Extracted plan from messages: %s", plan.goal[:50])
                return True

        return False

    def _parse_plan_from_content(self, content: str) -> TaskPlan | None:
        """从内容中解析计划"""
        # 查找计划/步骤列表模式
        patterns = [
            r"(?:计划|步骤|方案|plan|steps?)[:：]\s*\n((?:\s*[-*\d]+[.)]\s*.+\n?)+)",
            r"(?:我(?:将|会)|I will|Let me).*?[:：]\s*\n((?:\s*[-*\d]+[.)]\s*.+\n?)+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                steps_text = match.group(1)
                steps = self._parse_steps(steps_text)
                if steps:
                    # 提取目标
                    goal_match = re.search(
                        r"(?:目标|任务|goal|task)[:：]\s*(.+?)(?:\n|$)",
                        content,
                        re.IGNORECASE,
                    )
                    goal = goal_match.group(1) if goal_match else "完成用户请求"

                    return TaskPlan(goal=goal, steps=steps)

        return None

    def _parse_steps(self, steps_text: str) -> list[PlanStep]:
        """解析步骤列表"""
        steps = []
        # 匹配列表项
        items = re.findall(r"[-*\d]+[.)]\s*(.+?)(?=\n[-*\d]+[.)]|\n\n|$)", steps_text, re.DOTALL)

        for i, item in enumerate(items):
            description = item.strip()
            if not description:
                continue

            # 推断任务类型
            task_type = self._infer_task_type(description)

            steps.append(
                PlanStep(
                    id=f"step_{i}",
                    description=description,
                    task_type=task_type,
                )
            )

        return steps

    def _infer_task_type(self, description: str) -> TaskType:
        """推断任务类型"""
        desc_lower = description.lower()

        # 任务类型关键词映射
        type_keywords = {
            TaskType.ANALYSIS: ["分析", "理解", "研究", "analyze", "understand", "research"],
            TaskType.PLANNING: ["计划", "设计", "方案", "plan", "design"],
            TaskType.IMPLEMENTATION: [
                "实现",
                "编写",
                "创建",
                "implement",
                "write",
                "create",
                "build",
            ],
            TaskType.TESTING: ["测试", "验证", "test", "verify"],
            TaskType.DEBUGGING: ["调试", "修复", "debug", "fix"],
            TaskType.REVIEW: ["评审", "检查", "review", "check"],
            TaskType.DOCUMENTATION: ["文档", "document", "doc"],
        }

        for task_type, keywords in type_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                return task_type

        return TaskType.OTHER

    def update_step_status(
        self,
        step_id: str,
        status: TaskStatus,
        artifacts: list[str] | None = None,
        notes: str = "",
    ) -> None:
        """
        更新步骤状态

        Args:
            step_id: 步骤 ID
            status: 新状态
            artifacts: 产出列表
            notes: 备注
        """
        if not self._plan:
            return

        for step in self._plan.steps:
            if step.id == step_id:
                old_status = step.status
                step.status = status

                if artifacts:
                    step.artifacts.extend(artifacts)
                if notes:
                    step.notes = notes

                if status == TaskStatus.COMPLETED:
                    step.completed_at = datetime.now(UTC)

                self._plan.updated_at = datetime.now(UTC)

                # 检测阶段变更
                if old_status != status:
                    self._check_phase_change()

                logger.info(
                    "Step %s status: %s -> %s",
                    step_id,
                    old_status.value,
                    status.value,
                )
                break

    def advance_to_next_step(self) -> PlanStep | None:
        """
        推进到下一步

        Returns:
            新的当前步骤，如果已完成所有步骤则返回 None
        """
        if not self._plan:
            return None

        # 标记当前步骤为完成
        current = self._plan.current_step
        if current and current.status != TaskStatus.COMPLETED:
            current.status = TaskStatus.COMPLETED
            current.completed_at = datetime.now(UTC)

        # 推进到下一步
        self._plan.current_step_idx += 1
        self._plan.updated_at = datetime.now(UTC)

        # 检测阶段变更
        self._check_phase_change()

        return self._plan.current_step

    def _check_phase_change(self) -> None:
        """检测阶段变更"""
        if not self._plan or not self._plan.current_step:
            return

        current_phase = self._plan.current_step.task_type.value
        if self._last_phase and current_phase != self._last_phase:
            self._phase_changed = True
            logger.info(
                "Phase changed: %s -> %s",
                self._last_phase,
                current_phase,
            )
        self._last_phase = current_phase

    def get_relevant_steps(self, current_query: str) -> list[PlanStep]:
        """
        获取与当前查询相关的步骤

        用于计划感知的上下文选择。

        Args:
            current_query: 当前查询

        Returns:
            相关步骤列表
        """
        if not self._plan:
            return []

        relevant = []
        query_lower = current_query.lower()

        for step in self._plan.steps:
            # 当前步骤总是相关
            if step == self._plan.current_step:
                relevant.append(step)
                continue

            # 依赖的步骤相关
            if self._plan.current_step and step.id in (self._plan.current_step.dependencies or []):
                relevant.append(step)
                continue

            # 内容匹配的步骤相关
            if any(word in step.description.lower() for word in query_lower.split()):
                relevant.append(step)

        return relevant

    def get_message_relevance(
        self,
        message_index: int,
        message_content: str,
    ) -> float:
        """
        计算消息与当前计划的相关性

        Args:
            message_index: 消息索引
            message_content: 消息内容

        Returns:
            相关性分数 (0.0 - 1.0)
        """
        if not self._plan:
            return 0.5  # 无计划时返回中等相关性

        relevance = 0.0
        content_lower = message_content.lower()

        # 1. 检查是否与当前步骤相关
        current = self._plan.current_step
        if current:
            if any(word in content_lower for word in current.description.lower().split()):
                relevance += 0.4

            # 检查是否与当前步骤的产出相关
            for artifact in current.artifacts:
                if artifact.lower() in content_lower:
                    relevance += 0.3

        # 2. 检查是否与待完成步骤相关
        for step in self._plan.pending_steps:
            if any(word in content_lower for word in step.description.lower().split()):
                relevance += 0.2

        # 3. 检查是否与已完成步骤相关（较低权重）
        for step in self._plan.completed_steps:
            if message_index in step.related_messages:
                relevance += 0.1

        # 4. 检查是否包含目标关键词
        if any(word in content_lower for word in self._plan.goal.lower().split()):
            relevance += 0.2

        return min(1.0, relevance)

    def link_message_to_step(self, message_index: int, step_id: str) -> None:
        """
        将消息关联到步骤

        Args:
            message_index: 消息索引
            step_id: 步骤 ID
        """
        if not self._plan:
            return

        for step in self._plan.steps:
            if step.id == step_id:
                if message_index not in step.related_messages:
                    step.related_messages.append(message_index)
                break

    def get_plan_summary(self) -> str:
        """
        获取计划摘要

        用于注入到上下文中。

        Returns:
            计划摘要文本
        """
        if not self._plan:
            return ""

        lines = [f"目标: {self._plan.goal}"]
        lines.append(f"进度: {self._plan.progress:.0%}")
        lines.append("")

        for i, step in enumerate(self._plan.steps):
            status_icon = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.BLOCKED: "🚫",
            }.get(step.status, "❓")

            current_marker = " ← 当前" if step == self._plan.current_step else ""
            lines.append(f"{i + 1}. {status_icon} {step.description}{current_marker}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        if not self._plan:
            return {}

        return {
            "goal": self._plan.goal,
            "progress": self._plan.progress,
            "current_step_idx": self._plan.current_step_idx,
            "steps": [
                {
                    "id": s.id,
                    "description": s.description,
                    "type": s.task_type.value,
                    "status": s.status.value,
                    "artifacts": s.artifacts,
                }
                for s in self._plan.steps
            ],
        }
