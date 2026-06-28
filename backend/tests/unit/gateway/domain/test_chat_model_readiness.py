"""chat_model_readiness 单元测试。"""

from domains.gateway.domain.catalog.chat_model_readiness import (
    CHAT_READINESS_NEEDS_CONNECTIVITY,
    CHAT_READINESS_NEEDS_CREDENTIAL,
    CHAT_READINESS_NEEDS_MODEL,
    chat_readiness_error_code,
    chat_readiness_message,
    classify_chat_readiness,
)


def test_classify_ready_when_requestable_models_exist() -> None:
    assert (
        classify_chat_readiness(
            active_credential_count=0,
            requestable_model_count=2,
            total_model_count=2,
        )
        == "ready"
    )


def test_classify_needs_model_when_credentials_but_no_requestable() -> None:
    assert (
        classify_chat_readiness(
            active_credential_count=1,
            requestable_model_count=0,
            total_model_count=0,
        )
        == "needs_model"
    )


def test_classify_needs_connectivity_when_models_exist_but_unavailable() -> None:
    assert (
        classify_chat_readiness(
            active_credential_count=1,
            requestable_model_count=0,
            total_model_count=3,
        )
        == "needs_connectivity_fix"
    )


def test_classify_needs_credential_when_no_credentials() -> None:
    assert (
        classify_chat_readiness(
            active_credential_count=0,
            requestable_model_count=0,
            total_model_count=0,
        )
        == "needs_credential"
    )


def test_readiness_messages_and_codes() -> None:
    assert "凭据" in chat_readiness_message("needs_credential")
    assert "注册" in chat_readiness_message("needs_model")
    assert chat_readiness_error_code("needs_credential") == CHAT_READINESS_NEEDS_CREDENTIAL
    assert chat_readiness_error_code("needs_model") == CHAT_READINESS_NEEDS_MODEL
    assert chat_readiness_error_code("needs_connectivity_fix") == CHAT_READINESS_NEEDS_CONNECTIVITY
