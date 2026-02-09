"""
匿名数据迁移测试

测试登录/注册时将匿名用户数据迁移到正式账号的逻辑：
1. 迁移服务同时处理 sessions 和 video_gen_tasks
2. 仅迁移 user_id IS NULL 的记录（防止重复）
3. UserManager 的 on_after_login/on_after_register 钩子触发迁移
"""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.identity.application.session_migration_service import (
    AnonymousDataMigrationService,
    MigrationResult,
    migrate_anonymous_data_on_auth,
)

# =============================================================================
# AnonymousDataMigrationService 测试
# =============================================================================


@pytest.mark.unit
class TestAnonymousDataMigrationService:
    """匿名数据迁移服务测试"""

    def _mock_execute_result(self, row_count: int) -> MagicMock:
        """创建模拟的 SQL 执行结果"""
        result = MagicMock()
        result.fetchall.return_value = [MagicMock()] * row_count
        return result

    @pytest.mark.asyncio
    async def test_migrate_sessions_and_video_tasks(self):
        """测试: 同时迁移 sessions 和 video_gen_tasks"""
        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        anonymous_id = str(uuid.uuid4())

        # 模拟: 3 个 session + 2 个 video_task 被迁移
        mock_db.execute.side_effect = [
            self._mock_execute_result(3),  # sessions
            self._mock_execute_result(2),  # video_gen_tasks
        ]

        service = AnonymousDataMigrationService(mock_db)
        result = await service.migrate(user_id, anonymous_id)

        assert result.sessions == 3
        assert result.video_tasks == 2
        assert result.total == 5
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_migrate_no_anonymous_data(self):
        """测试: 无匿名数据时返回零"""
        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        anonymous_id = str(uuid.uuid4())

        mock_db.execute.side_effect = [
            self._mock_execute_result(0),  # sessions
            self._mock_execute_result(0),  # video_gen_tasks
        ]

        service = AnonymousDataMigrationService(mock_db)
        result = await service.migrate(user_id, anonymous_id)

        assert result.sessions == 0
        assert result.video_tasks == 0
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_migrate_with_string_user_id(self):
        """测试: 支持字符串格式的 user_id"""
        mock_db = AsyncMock()
        user_id_str = str(uuid.uuid4())
        anonymous_id = str(uuid.uuid4())

        mock_db.execute.side_effect = [
            self._mock_execute_result(1),
            self._mock_execute_result(0),
        ]

        service = AnonymousDataMigrationService(mock_db)
        result = await service.migrate(user_id_str, anonymous_id)

        assert result.sessions == 1
        assert result.video_tasks == 0

        # 验证传给 SQL 的 user_id 是 UUID 类型
        call_args = mock_db.execute.call_args_list[0]
        params = call_args[0][1]  # 第二个位置参数是参数字典
        assert isinstance(params["user_id"], uuid.UUID)

    @pytest.mark.asyncio
    async def test_migrate_sql_contains_user_id_is_null_guard(self):
        """测试: SQL 包含 user_id IS NULL 条件（防止覆盖已绑定的数据）"""
        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        anonymous_id = str(uuid.uuid4())

        mock_db.execute.side_effect = [
            self._mock_execute_result(0),
            self._mock_execute_result(0),
        ]

        service = AnonymousDataMigrationService(mock_db)
        await service.migrate(user_id, anonymous_id)

        # 验证两条 SQL 都包含 user_id IS NULL 保护
        for call in mock_db.execute.call_args_list:
            sql_text = str(call[0][0])
            assert "user_id IS NULL" in sql_text, (
                f"SQL should contain 'user_id IS NULL' guard: {sql_text}"
            )


# =============================================================================
# migrate_anonymous_data_on_auth 便捷函数测试
# =============================================================================


@pytest.mark.unit
class TestMigrateOnAuth:
    """认证后迁移便捷函数测试"""

    @pytest.mark.asyncio
    async def test_no_anonymous_id_returns_empty_result(self):
        """测试: 无匿名 ID 时直接返回空结果"""
        mock_db = AsyncMock()
        result = await migrate_anonymous_data_on_auth(mock_db, uuid.uuid4(), None)

        assert result.total == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_anonymous_id_returns_empty_result(self):
        """测试: 空字符串匿名 ID 也返回空结果"""
        mock_db = AsyncMock()
        result = await migrate_anonymous_data_on_auth(mock_db, uuid.uuid4(), "")

        assert result.total == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_anonymous_id_calls_migrate(self):
        """测试: 有匿名 ID 时触发迁移"""
        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        anonymous_id = str(uuid.uuid4())

        # Mock execute 返回
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        result = await migrate_anonymous_data_on_auth(mock_db, user_id, anonymous_id)

        assert isinstance(result, MigrationResult)
        assert mock_db.execute.call_count == 2  # sessions + video_gen_tasks


# =============================================================================
# UserManager 钩子测试
# =============================================================================


@pytest.mark.unit
class TestUserManagerMigrationHooks:
    """UserManager 登录/注册钩子触发迁移测试"""

    def _create_mock_user(self) -> MagicMock:
        """创建 Mock User"""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.email = "leo@example.com"
        user.name = "Leo"
        return user

    def _create_mock_request(self, anonymous_cookie: str | None = None) -> MagicMock:
        """创建 Mock Request"""
        request = MagicMock()
        cookies = {}
        if anonymous_cookie:
            cookies["anonymous_user_id"] = anonymous_cookie
        request.cookies = cookies
        return request

    @pytest.mark.asyncio
    async def test_on_after_login_triggers_migration(self):
        """测试: 登录后钩子触发匿名数据迁移"""
        from domains.identity.infrastructure.user_manager import UserManager

        anonymous_id = str(uuid.uuid4())
        user = self._create_mock_user()
        request = self._create_mock_request(anonymous_cookie=anonymous_id)

        mock_user_db = MagicMock()
        mock_user_db.session = AsyncMock()

        manager = UserManager(mock_user_db)

        with patch(
            "domains.identity.infrastructure.user_manager.migrate_anonymous_data_on_auth",
            new_callable=AsyncMock,
            return_value=MigrationResult(sessions=1, video_tasks=2),
        ) as mock_migrate:
            await manager.on_after_login(user, request=request)

            mock_migrate.assert_called_once_with(
                mock_user_db.session,
                user.id,
                anonymous_id,
            )

    @pytest.mark.asyncio
    async def test_on_after_login_no_cookie_skips_migration(self):
        """测试: 无匿名 Cookie 时不触发迁移"""
        from domains.identity.infrastructure.user_manager import UserManager

        user = self._create_mock_user()
        request = self._create_mock_request(anonymous_cookie=None)

        mock_user_db = MagicMock()
        manager = UserManager(mock_user_db)

        with patch(
            "domains.identity.infrastructure.user_manager.migrate_anonymous_data_on_auth",
            new_callable=AsyncMock,
        ) as mock_migrate:
            await manager.on_after_login(user, request=request)

            mock_migrate.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_after_login_no_request_skips_migration(self):
        """测试: 无 Request 时不触发迁移"""
        from domains.identity.infrastructure.user_manager import UserManager

        user = self._create_mock_user()
        mock_user_db = MagicMock()
        manager = UserManager(mock_user_db)

        with patch(
            "domains.identity.infrastructure.user_manager.migrate_anonymous_data_on_auth",
            new_callable=AsyncMock,
        ) as mock_migrate:
            await manager.on_after_login(user, request=None)

            mock_migrate.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_after_register_triggers_migration(self):
        """测试: 注册后钩子也触发匿名数据迁移"""
        from domains.identity.infrastructure.user_manager import UserManager

        anonymous_id = str(uuid.uuid4())
        user = self._create_mock_user()
        request = self._create_mock_request(anonymous_cookie=anonymous_id)

        mock_user_db = MagicMock()
        mock_user_db.session = AsyncMock()

        manager = UserManager(mock_user_db)

        with patch(
            "domains.identity.infrastructure.user_manager.migrate_anonymous_data_on_auth",
            new_callable=AsyncMock,
            return_value=MigrationResult(sessions=2, video_tasks=0),
        ) as mock_migrate:
            await manager.on_after_register(user, request=request)

            mock_migrate.assert_called_once_with(
                mock_user_db.session,
                user.id,
                anonymous_id,
            )
