"""GatewayModel deployment weight 不变量。

LiteLLM Router 在 ``simple_shuffle`` / ``weighted-pick`` 策略下，按 deployment 的
``litellm_params.weight`` 做加权随机抽样：

- 必须为 **正整数**（``>= 1``）；
- ``0`` 或负值会导致该 deployment 永远命不中，等同隐式禁用，违反路由可观测性；
- 非数字（``None`` / ``"abc"``）通常源于历史脏数据或客户端误传。

写入侧（``application``、``presentation``）使用 :func:`assert_deployment_weight`
严格拒绝非法值；读取侧（``infrastructure``）使用 :func:`coerce_deployment_weight`
容错回退为 ``MIN_DEPLOYMENT_WEIGHT``，避免历史数据让 Router 启动失败。
"""

from __future__ import annotations

from typing import Any, Final

from libs.exceptions import ValidationError

MIN_DEPLOYMENT_WEIGHT: Final[int] = 1


def coerce_deployment_weight(value: Any) -> int:
    """读取侧容错：非法值兜底为 ``MIN_DEPLOYMENT_WEIGHT``。

    供 ``router_singleton`` 等基础设施在拼装 ``model_list`` 时使用——
    历史脏数据不应让 Router 启动失败，但应被规整到合法范围。
    """
    try:
        weight = int(value)
    except (TypeError, ValueError):
        return MIN_DEPLOYMENT_WEIGHT
    return weight if weight >= MIN_DEPLOYMENT_WEIGHT else MIN_DEPLOYMENT_WEIGHT


def assert_deployment_weight(value: Any, *, field_name: str = "weight") -> int:
    """写入侧严格：非正整数抛 :class:`ValidationError`。

    供 application / presentation 在接收用户输入时使用。返回规范化后的 ``int``，
    与 ORM ``GatewayModel.weight`` 列类型对齐。
    """
    try:
        weight = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} 必须为正整数") from exc
    if weight < MIN_DEPLOYMENT_WEIGHT:
        raise ValidationError(f"{field_name} 必须为正整数")
    return weight


__all__ = [
    "MIN_DEPLOYMENT_WEIGHT",
    "assert_deployment_weight",
    "coerce_deployment_weight",
]
