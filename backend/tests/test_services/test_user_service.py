"""
User Service Tests - 用户服务测试
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.user import UserService


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession) -> None:
    """测试创建用户"""
    service = UserService(db_session)

    user = await service.create(
        email="new@example.com",
        password="password123",
        name="New User",
    )

    assert user.email == "new@example.com"
    assert user.name == "New User"
    assert user.password_hash != "password123"  # 密码应该被哈希


@pytest.mark.asyncio
async def test_get_by_email(db_session: AsyncSession) -> None:
    """测试通过邮箱获取用户"""
    service = UserService(db_session)

    # 创建用户
    await service.create(
        email="find@example.com",
        password="password123",
        name="Find User",
    )

    # 查找用户
    user = await service.get_by_email("find@example.com")
    assert user is not None
    assert user.email == "find@example.com"

    # 查找不存在的用户
    not_found = await service.get_by_email("notfound@example.com")
    assert not_found is None


@pytest.mark.asyncio
async def test_authenticate_success(db_session: AsyncSession) -> None:
    """测试认证成功"""
    service = UserService(db_session)

    # 创建用户
    await service.create(
        email="auth@example.com",
        password="correct_password",
        name="Auth User",
    )

    # 认证成功
    user = await service.authenticate("auth@example.com", "correct_password")
    assert user.email == "auth@example.com"


@pytest.mark.asyncio
async def test_authenticate_failure(db_session: AsyncSession) -> None:
    """测试认证失败"""
    from exceptions import AuthenticationError

    service = UserService(db_session)

    # 创建用户
    await service.create(
        email="authfail@example.com",
        password="correct_password",
        name="Auth Fail User",
    )

    # 密码错误
    with pytest.raises(AuthenticationError):
        await service.authenticate("authfail@example.com", "wrong_password")

    # 用户不存在
    with pytest.raises(AuthenticationError):
        await service.authenticate("notexist@example.com", "any_password")


@pytest.mark.asyncio
async def test_password_hashing(db_session: AsyncSession) -> None:
    """测试密码哈希"""
    service = UserService(db_session)

    password = "test_password_123"
    hashed = service._hash_password(password)

    # 验证哈希后的密码与原密码不同
    assert hashed != password

    # 验证密码验证功能
    assert service._verify_password(password, hashed)
    assert not service._verify_password("wrong_password", hashed)


@pytest.mark.asyncio
async def test_create_token(db_session: AsyncSession) -> None:
    """测试创建 Token"""
    service = UserService(db_session)

    user = await service.create(
        email="token@example.com",
        password="password123",
        name="Token User",
    )

    token_pair = await service.create_token(user)

    assert token_pair.access_token is not None
    assert len(token_pair.access_token) > 0
    assert token_pair.expires_in > 0


@pytest.mark.asyncio
async def test_get_user_from_token(db_session: AsyncSession) -> None:
    """测试从 Token 获取用户"""
    service = UserService(db_session)

    user = await service.create(
        email="fromtoken@example.com",
        password="password123",
        name="From Token User",
    )

    token_pair = await service.create_token(user)
    retrieved_user = await service.get_user_from_token(token_pair.access_token)

    assert retrieved_user is not None
    assert retrieved_user.id == user.id
    assert retrieved_user.email == user.email


@pytest.mark.asyncio
async def test_get_user_from_invalid_token(db_session: AsyncSession) -> None:
    """测试无效 Token"""
    service = UserService(db_session)

    user = await service.get_user_from_token("invalid_token")
    assert user is None
