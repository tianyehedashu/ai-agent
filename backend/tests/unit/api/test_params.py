"""libs.api.params UUID 解析。"""

from __future__ import annotations

import uuid

import pytest

from libs.api.params import coerce_optional_uuid, parse_optional_uuid
from libs.exceptions import ValidationError


@pytest.mark.unit
class TestCoerceOptionalUuid:
    def test_none_and_empty(self) -> None:
        assert coerce_optional_uuid(None) is None
        assert coerce_optional_uuid("") is None

    def test_uuid_instance(self) -> None:
        uid = uuid.uuid4()
        assert coerce_optional_uuid(uid) == uid

    def test_uuid_string(self) -> None:
        uid = uuid.uuid4()
        assert coerce_optional_uuid(str(uid)) == uid

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError, match="valid UUID"):
            coerce_optional_uuid("not-a-uuid")


@pytest.mark.unit
class TestParseOptionalUuid:
    def test_invalid_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError, match="Invalid session_id"):
            parse_optional_uuid("bad", param_name="session_id")
