"""
PII Guardrail 单元测试：脱敏正则覆盖手机/邮箱/身份证/银行卡/IP。
"""

from __future__ import annotations

from domains.gateway.infrastructure.guardrails.pii_guardrail import (
    hash_original,
    redact_messages,
    redact_text,
)


def test_redact_phone():
    redacted, hits = redact_text("联系方式 13912345678 请保密")
    assert "13912345678" not in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "redacted_phone" in hits


def test_redact_email():
    redacted, hits = redact_text("发邮件给 alice@example.com 即可")
    assert "alice@example.com" not in redacted
    assert "redacted_email" in hits


def test_redact_idcard():
    redacted, hits = redact_text("身份证：11010519900101001X 已存档")
    assert "11010519900101001X" not in redacted
    assert "redacted_id" in hits


def test_redact_bank_card():
    redacted, hits = redact_text("卡号 6225760080000000 转账")
    # 至少命中银行卡或身份证规则之一（本质上都是连续数字 redact 兜底）
    assert "6225760080000000" not in redacted
    assert hits


def test_redact_ipv4():
    redacted, hits = redact_text("Source 192.168.1.10 ; target 10.0.0.1")
    assert "192.168.1.10" not in redacted
    assert "10.0.0.1" not in redacted
    assert "redacted_ip" in hits


def test_redact_messages_preserves_other_fields():
    messages = [
        {"role": "user", "content": "我的手机是 13800138000"},
        {"role": "assistant", "content": "好的，已记下"},
    ]
    redacted, hits = redact_messages(messages)
    assert redacted[0]["content"] != messages[0]["content"]
    assert redacted[1]["content"] == messages[1]["content"]
    assert "redacted_phone" in hits


def test_hash_original_stable():
    a = hash_original("hello world")
    b = hash_original("hello world")
    assert a == b
    assert len(a) == 64
