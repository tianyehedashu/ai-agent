"""credential_model_cascade 纯函数测试。"""

from domains.gateway.domain.credential.credential_model_cascade import (
    apply_credential_cascade_disable_tags,
    clear_credential_cascade_disable_tags,
    was_credential_cascade_disabled,
)
from domains.gateway.domain.types import CREDENTIAL_CASCADE_DISABLED_TAG


def test_apply_and_clear_cascade_tags() -> None:
    tagged = apply_credential_cascade_disable_tags({"managed_by": "config"})
    assert tagged[CREDENTIAL_CASCADE_DISABLED_TAG] is True
    assert tagged["managed_by"] == "config"
    assert was_credential_cascade_disabled(tagged)

    cleared = clear_credential_cascade_disable_tags(tagged)
    assert cleared == {"managed_by": "config"}
    assert not was_credential_cascade_disabled(cleared)


def test_clear_cascade_tags_noop_without_marker() -> None:
    assert clear_credential_cascade_disable_tags(None) is None
    assert clear_credential_cascade_disable_tags({"k": 1}) == {"k": 1}
