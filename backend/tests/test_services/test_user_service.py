"""
User Service Tests - 用户服务测试
"""

import pytest

from services.user import UserService


@pytest.mark.asyncio
async def test_create_user() -> None:
    """测试创建用户"""
    UserService()

    # TODO: 添加数据库 mock
    # user = await service.create(
    #     email="new@example.com",
    #     password="password123",
    #     name="New User",
    # )
    # assert user.email == "new@example.com"


@pytest.mark.asyncio
async def test_password_hashing() -> None:
    """测试密码哈希"""
    service = UserService()

    password = "test_password_123"
    hashed = service._hash_password(password)

    # 验证哈希后的密码与原密码不同
    assert hashed != password

    # 验证密码验证功能
    assert service._verify_password(password, hashed)
    assert not service._verify_password("wrong_password", hashed)
