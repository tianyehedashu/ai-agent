"""
虚拟 Key 生成、验证、掩码 - 单元测试。
"""

from __future__ import annotations

from domains.gateway.domain.virtual_key_service import (
    VKEY_KEY_ID_LENGTH,
    VKEY_PREFIX,
    VKEY_SECRET_LENGTH,
    extract_key_id,
    generate_vkey,
    hash_vkey,
    is_vkey_format,
    mask_vkey,
    verify_vkey,
)


def test_generate_vkey_format():
    plain, key_id, key_hash = generate_vkey()
    assert plain.startswith(VKEY_PREFIX)
    assert len(key_id) == VKEY_KEY_ID_LENGTH
    assert is_vkey_format(plain)
    assert verify_vkey(plain, key_hash)


def test_generate_vkey_unique():
    keys = {generate_vkey()[0] for _ in range(50)}
    assert len(keys) == 50, "vkey 应当各不相同"


def test_hash_deterministic():
    plain, _, _ = generate_vkey()
    assert hash_vkey(plain) == hash_vkey(plain)


def test_verify_wrong_key_fails():
    plain, _, key_hash = generate_vkey()
    other_plain, _, _ = generate_vkey()
    assert verify_vkey(plain, key_hash)
    assert not verify_vkey(other_plain, key_hash)


def test_extract_key_id():
    plain, key_id, _ = generate_vkey()
    assert extract_key_id(plain) == key_id


def test_mask_vkey():
    plain, _, _ = generate_vkey()
    masked = mask_vkey(plain)
    assert masked.startswith(VKEY_PREFIX)
    assert masked.endswith(plain[-4:])
    assert "..." in masked


def test_invalid_format_detected():
    assert not is_vkey_format("sk-other-something")
    assert not is_vkey_format("sk-gw-short")
    assert not is_vkey_format("sk-gw-" + "g" * VKEY_KEY_ID_LENGTH + "-" + "h" * VKEY_SECRET_LENGTH)


def test_full_length_constant_consistent():
    plain, _, _ = generate_vkey()
    # full length = prefix + key_id + 1 (separator) + secret
    expected = len(VKEY_PREFIX) + VKEY_KEY_ID_LENGTH + 1 + VKEY_SECRET_LENGTH
    assert len(plain) == expected
