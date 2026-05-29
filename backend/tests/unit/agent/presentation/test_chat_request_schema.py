"""ChatRequest schema：strict 模式下 JSON UUID 字符串。"""

from __future__ import annotations

import uuid

import pytest

from domains.agent.presentation.chat_router import ChatRequest, ResumeRequest


@pytest.mark.unit
def test_chat_request_accepts_gateway_team_id_string() -> None:
    team_id = uuid.uuid4()
    req = ChatRequest.model_validate(
        {
            "message": "hi",
            "gateway_team_id": str(team_id),
        }
    )
    assert req.gateway_team_id == team_id


@pytest.mark.unit
def test_resume_request_accepts_gateway_team_id_string() -> None:
    team_id = uuid.uuid4()
    req = ResumeRequest.model_validate(
        {
            "session_id": "sess-1",
            "checkpoint_id": "ckpt-1",
            "action": "approve",
            "gateway_team_id": str(team_id),
        }
    )
    assert req.gateway_team_id == team_id
