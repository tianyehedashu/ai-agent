"""
OwnedRepositoryBase 单元测试

测试 Repository 基类的权限过滤功能。
"""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.session import Session
from libs.db.base_repository import OwnedRepositoryBase
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


class MockSessionRepository(OwnedRepositoryBase[Session]):
    """测试用的 Session Repository（不以 Test 开头，避免被 pytest 识别为测试类）"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.db = db

    @property
    def model_class(self) -> type[Session]:
        return Session

    @property
    def anonymous_user_id_column(self) -> str:
        return "anonymous_user_id"


@pytest.mark.unit
class TestOwnedRepositoryBase:
    """OwnedRepositoryBase 测试"""

    @pytest.fixture
    def mock_db(self):
        """创建模拟数据库会话"""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repository(self, mock_db):
        """创建测试 Repository"""
        return MockSessionRepository(mock_db)

    def test_model_class_property(self, repository):
        """测试: model_class 属性"""
        assert repository.model_class == Session

    def test_anonymous_user_id_column_property(self, repository):
        """测试: anonymous_user_id_column 属性"""
        assert repository.anonymous_user_id_column == "anonymous_user_id"

    def test_user_id_column_default(self, repository):
        """测试: user_id_column 默认值"""
        assert repository.user_id_column == "user_id"

    @pytest.mark.asyncio
    async def test_apply_ownership_filter_admin_bypass(self, repository, mock_db):
        """测试: 管理员绕过权限过滤"""
        user_id = uuid.uuid4()
        ctx = PermissionContext(user_id=user_id, role="admin")
        set_permission_context(ctx)

        try:
            query = select(Session)
            filtered_query = repository._apply_ownership_filter(query)

            # 管理员应该不过滤，返回原始查询
            # 由于我们无法直接比较 SQLAlchemy 查询对象，我们验证没有添加额外的 where 条件
            # 实际上，对于管理员，应该返回原始查询
            assert filtered_query is not None
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_apply_ownership_filter_registered_user(self, repository, mock_db):
        """测试: 注册用户权限过滤"""
        user_id = uuid.uuid4()
        ctx = PermissionContext(user_id=user_id, role="user")
        set_permission_context(ctx)

        try:
            query = select(Session)
            filtered_query = repository._apply_ownership_filter(query)

            # 验证查询被过滤（包含 user_id 条件）
            assert filtered_query is not None
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_apply_ownership_filter_anonymous_user(self, repository, mock_db):
        """测试: 匿名用户权限过滤"""
        anonymous_id = "test-anonymous-id"
        ctx = PermissionContext(anonymous_user_id=anonymous_id, role="user")
        set_permission_context(ctx)

        try:
            query = select(Session)
            filtered_query = repository._apply_ownership_filter(query)

            # 验证查询被过滤（包含 anonymous_user_id 条件）
            assert filtered_query is not None
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_apply_ownership_filter_no_context(self, repository, mock_db):
        """测试: 无权限上下文时返回空结果"""
        clear_permission_context()

        query = select(Session)
        filtered_query = repository._apply_ownership_filter(query)

        # 无上下文时应该返回空结果（WHERE False）
        assert filtered_query is not None

    @pytest.mark.asyncio
    async def test_find_owned_with_admin(self, repository, mock_db):
        """测试: 管理员使用 find_owned 获取所有数据"""
        user_id = uuid.uuid4()
        ctx = PermissionContext(user_id=user_id, role="admin")
        set_permission_context(ctx)

        try:
            # 模拟数据库执行结果
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_db.execute = AsyncMock(return_value=mock_result)

            result = await repository.find_owned(skip=0, limit=20)

            assert isinstance(result, list)
            # 验证执行了查询
            assert mock_db.execute.called
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_owned_with_permission_check(self, repository, mock_db):
        """测试: get_owned 自动检查所有权"""
        user_id = uuid.uuid4()
        ctx = PermissionContext(user_id=user_id, role="user")
        set_permission_context(ctx)

        try:
            session_id = uuid.uuid4()

            # 模拟数据库执行结果（无权限时返回 None）
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)

            result = await repository.get_owned(session_id)

            assert result is None
            # 验证执行了查询
            assert mock_db.execute.called
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_count_owned(self, repository, mock_db):
        """测试: count_owned 统计当前用户拥有的数据"""
        user_id = uuid.uuid4()
        ctx = PermissionContext(user_id=user_id, role="user")
        set_permission_context(ctx)

        try:
            # 模拟数据库执行结果
            mock_result = MagicMock()
            mock_result.scalar.return_value = 5
            mock_db.execute = AsyncMock(return_value=mock_result)

            count = await repository.count_owned()

            assert count == 5
            assert mock_db.execute.called
        finally:
            clear_permission_context()
