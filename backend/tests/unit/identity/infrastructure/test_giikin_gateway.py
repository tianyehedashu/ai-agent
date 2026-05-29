"""giikin_gateway.parse_gateway_identity 单元测试。"""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

from pydantic import SecretStr
import pytest

from bootstrap.config import Settings
from domains.identity.infrastructure.auth.giikin_gateway import (
    GiikinGatewayClaims,
    parse_gateway_identity,
)
from libs.exceptions import AuthenticationError


def _settings(*, internal_key: str | None = "test-internal-key") -> Settings:
    return Settings(
        auth_mode="sso",
        giikin_internal_key=SecretStr(internal_key) if internal_key is not None else None,
        giikin_user_json_header="X-Giikin-User-JSON",
        giikin_user_id_header="X-Giikin-User-Id",
        giikin_internal_key_header="X-Giikin-Internal-Key",
    )


def _request(headers: dict[str, str]) -> SimpleNamespace:
    return SimpleNamespace(headers=headers)


def _encode_user_json(payload: dict[str, object]) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


@pytest.mark.unit
class TestParseGatewayIdentity:
    def test_no_identity_headers_returns_none(self) -> None:
        claims = parse_gateway_identity(_request({}), _settings())
        assert claims is None

    def test_missing_internal_key_raises(self) -> None:
        headers = {
            "X-Giikin-User-JSON": _encode_user_json({"user_id": "1001", "name": "Leo"}),
        }
        with pytest.raises(AuthenticationError, match="Invalid gateway internal key"):
            parse_gateway_identity(_request(headers), _settings())

    def test_mismatched_internal_key_raises(self) -> None:
        headers = {
            "X-Giikin-User-JSON": _encode_user_json({"user_id": "1001", "name": "Leo"}),
            "X-Giikin-Internal-Key": "wrong-key",
        }
        with pytest.raises(AuthenticationError, match="Invalid gateway internal key"):
            parse_gateway_identity(_request(headers), _settings())

    def test_valid_user_json_returns_claims(self) -> None:
        payload = {
            "user_id": "1001",
            "name": "Leo",
            "org_code": "ORG01",
            "shop_id": "SHOP9",
        }
        headers = {
            "X-Giikin-User-JSON": _encode_user_json(payload),
            "X-Giikin-Internal-Key": "test-internal-key",
        }

        claims = parse_gateway_identity(_request(headers), _settings())

        assert claims == GiikinGatewayClaims(
            user_id="1001",
            name="Leo",
            org_code="ORG01",
            shop_id="SHOP9",
        )

    def test_invalid_base64_raises(self) -> None:
        headers = {
            "X-Giikin-User-JSON": "%%%not-base64%%%",
            "X-Giikin-Internal-Key": "test-internal-key",
        }
        with pytest.raises(AuthenticationError, match="Invalid gateway identity header"):
            parse_gateway_identity(_request(headers), _settings())

    def test_missing_user_id_raises(self) -> None:
        headers = {
            "X-Giikin-User-JSON": _encode_user_json({"name": "No Id"}),
            "X-Giikin-Internal-Key": "test-internal-key",
        }
        with pytest.raises(AuthenticationError, match="Gateway identity missing user_id"):
            parse_gateway_identity(_request(headers), _settings())

    def test_user_id_header_only_with_valid_internal_key(self) -> None:
        headers = {
            "X-Giikin-User-Id": "2002",
            "X-Giikin-Internal-Key": "test-internal-key",
        }
        claims = parse_gateway_identity(_request(headers), _settings())
        assert claims == GiikinGatewayClaims(
            user_id="2002",
            name="Giikin 2002",
            org_code="",
            shop_id="",
        )

    def test_sso_mode_without_internal_key_is_rejected_at_config(self) -> None:
        """fail-closed：sso 模式缺 internal_key 时配置层直接拒绝，杜绝绕过网关伪造身份。"""
        with pytest.raises(ValueError, match="giikin_internal_key"):
            _settings(internal_key=None)
