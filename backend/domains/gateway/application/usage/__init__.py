"""usage 子包 — Gateway 用量可观测性与请求日志失败分类。

迁移自 application/ 根目录平铺文件（M6），详见
docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md。

子分组：
- vkey 指标：gateway_vkey_metrics（进程内计数，供 strict 决策与运营观察）
- 失败分类：request_log_failure_classification（异常 → RequestStatus + 稳定 error_code）
"""

from .gateway_vkey_metrics import (
    AMBIGUOUS_MODEL_INVOCATIONS_TOTAL,
    export_vkey_metrics,
    record_ambiguous_model_invocation,
    reset_vkey_metrics_for_tests,
)
from .request_log_failure_classification import (
    ClassifiedRequestLogFailure,
    classify_request_log_failure,
)

__all__ = [
    "AMBIGUOUS_MODEL_INVOCATIONS_TOTAL",
    "ClassifiedRequestLogFailure",
    "classify_request_log_failure",
    "export_vkey_metrics",
    "record_ambiguous_model_invocation",
    "reset_vkey_metrics_for_tests",
]
