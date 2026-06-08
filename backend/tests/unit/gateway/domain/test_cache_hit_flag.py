"""Prompt cache hit flag parsing rules."""

from domains.gateway.domain.cache_hit_flag import coerce_cache_hit_flag


def test_coerce_cache_hit_flag_accepts_explicit_true_values() -> None:
    assert coerce_cache_hit_flag(True) is True
    assert coerce_cache_hit_flag(1) is True
    assert coerce_cache_hit_flag("true") is True
    assert coerce_cache_hit_flag("YES") is True


def test_coerce_cache_hit_flag_rejects_truthy_false_strings() -> None:
    assert coerce_cache_hit_flag(False) is False
    assert coerce_cache_hit_flag(0) is False
    assert coerce_cache_hit_flag("false") is False
    assert coerce_cache_hit_flag("0") is False
    assert coerce_cache_hit_flag("no") is False
    assert coerce_cache_hit_flag("anything else") is False
