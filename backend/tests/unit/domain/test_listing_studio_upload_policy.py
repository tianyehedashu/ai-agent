"""upload_policy 单元测试。"""

import pytest

from domains.agent.domain.listing_studio.upload_policy import validate_image_upload
from libs.exceptions import ValidationError


@pytest.mark.unit
class TestValidateImageUpload:
    def test_accepts_png(self):
        ext = validate_image_upload("image/png", 1024, 10_485_760)
        assert ext == "png"

    def test_rejects_unknown_mime(self):
        with pytest.raises(ValidationError, match="仅支持"):
            validate_image_upload("application/pdf", 1024, 10_485_760)

    def test_rejects_empty_file(self):
        with pytest.raises(ValidationError, match="为空"):
            validate_image_upload("image/png", 0, 10_485_760)

    def test_rejects_oversized(self):
        with pytest.raises(ValidationError, match="不能超过"):
            validate_image_upload("image/jpeg", 11_000_000, 10_485_760)
