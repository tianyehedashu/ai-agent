"""代理业务错误映射：InvocationPolicyViolationError。"""

from domains.gateway.domain.errors import InvocationPolicyViolationError
from domains.gateway.presentation.gateway_proxy_business_error_classify import (
    classify_proxy_use_case_business_error,
)


def test_invocation_policy_violation_maps_400() -> None:
    failure = classify_proxy_use_case_business_error(
        InvocationPolicyViolationError("DashScope Qwen3 开启思考模式须 stream: true")
    )
    assert failure is not None
    assert failure.http_status == 400
    assert failure.openai_error_type == "invocation_policy_violation"
