"""upstream_rule_ids_from_call_data 单测。"""

from __future__ import annotations

import uuid

from domains.gateway.application.provider_quota_guard import upstream_rule_ids_from_call_data


def test_collects_all_reservation_rule_ids() -> None:
    rule_a = uuid.uuid4()
    rule_b = uuid.uuid4()
    data = {
        "metadata": {
            "gateway_provider_plan_id": str(rule_a),
            "gateway_provider_quota_reservations": [
                {"rule_id": str(rule_a), "quota_id": str(rule_a), "minute_unix": 1},
                {"quota_id": str(rule_b), "minute_unix": 2},
            ],
        },
        "litellm_params": {
            "metadata": {
                "gateway_provider_quota_reservations": [
                    {"rule_id": str(rule_b), "minute_unix": 2},
                ],
            },
        },
    }

    ids = upstream_rule_ids_from_call_data(data)

    assert ids == [rule_a, rule_b]
