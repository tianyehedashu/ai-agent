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
    AnonymousDataReassignmentService,
    MigrationResult,
    migrate_anonymous_data_on_auth,
)

# =============================================================================
# AnonymousDataReassignmentService 测试
# =============================================================================


@pytest.mark.unit
class TestAnonymousDataReassignmentService:
    """匿名数据归并服务测试"""

    def _make_service(
        self,
        *,
        session_count: int,
        video_task_count: int,
    ) -> tuple[AnonymousDataReassignmentService, AsyncMock, AsyncMock]:
        session_service = AsyncMock()
        video_task_service = AsyncMock()
        session_service.reassign_anonymous_to_user.return_value = session_count
        video_task_service.reassign_anonymous_to_user.return_value = video_task_count
        return (
            AnonymousDataReassignmentService(
                session_service=session_service,
                video_task_service=video_task_service,
            ),
            session_service,
            video_task_service,
        )

    @pytest.mark.asyncio
    async def test_migrate_sessions_and_video_tasks(self):
        """测试: 同时迁移 sessions 和 video_gen_tasks"""
        user_id = uuid.uuid4()
        anonymous_id = str(uuid.uuid4())

        service, session_service, video_task_service = self._make_service(
            session_count=3,
            video_task_count=2,
        )
        result = await service.migrate(user_id, anonymous_id)

        assert result.sessions == 3
        assert result.video_tasks == 2
        assert result.total == 5
        session_service.reassign_anonymous_to_user.assert_awaited_once_with(
            user_id=user_id,
            anonymous_user_id=anonymous_id,
        )
        video_task_service.reassign_anonymous_to_user.assert_awaited_once_with(
            user_id=user_id,
            anonymous_user_id=anonymous_id,
        )

    @pytest.mark.asyncio
    async def test_migrate_no_anonymous_data(self):
        """测试: 无匿名数据时返回零"""
        user_id = uuid.uuid4()
        anonymous_id = str(uuid.uuid4())

        service, _, _ = self._make_service(session_count=0, video_task_count=0)
        result = await service.migrate(user_id, anonymous_id)

        assert result.sessions == 0
        assert result.video_tasks == 0
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_migrate_with_string_user_id(self):
        """测试: 支持字符串格式的 user_id"""
        user_id_str = str(uuid.uuid4())
        anonymous_id = str(uuid.uuid4())

        service, session_service, _ = self._make_service(session_count=1, video_task_count=0)
        result = await service.migrate(user_id_str, anonymous_id)

        assert result.sessions == 1
        assert result.video_tasks == 0

        # 验证传给仓储的 user_id 是 UUID 类型
        call_kwargs = session_service.reassign_anonymous_to_user.call_args.kwargs
        assert isinstance(call_kwargs["user_id"], uuid.UUID)

    @pytest.mark.asyncio
    async def test_migrate_delegates_guard_to_repositories(self):
        """测试: 防覆盖保护由各域仓储封装，应用服务不写裸 SQL"""
        user_id = uuid.uuid4()
        anonymous_id = str(uuid.uuid4())

        service, session_service, video_task_service = self._make_service(
            session_count=0,
            video_task_count=0,
        )
        await service.migrate(user_id, anonymous_id)

        session_service.reassign_anonymous_to_user.assert_awaited_once()
        video_task_service.reassign_anonymous_to_user.assert_awaited_once()


# =============================================================================
# migrate_anonymous_data_on_auth 便捷函数测试
# =============================================================================


@pytest.mark.unit
class TestMigrateOnAuth:
    """认证后迁移便捷函数测试"""

    @pytest.mark.asyncio
    async def test_no_anonymous_id_returns_empty_result(self):
        """测试: 无匿名 ID 时直接返回空结果"""
        session_service = AsyncMock()
        video_task_service = AsyncMock()
        result = await migrate_anonymous_data_on_auth(
            uuid.uuid4(),
            None,
            session_service=session_service,
            video_task_service=video_task_service,
        )

        assert result.total == 0
        session_service.reassign_anonymous_to_user.assert_not_called()
        video_task_service.reassign_anonymous_to_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_anonymous_id_returns_empty_result(self):
        """测试: 空字符串匿名 ID 也返回空结果"""
        session_service = AsyncMock()
        video_task_service = AsyncMock()
        result = await migrate_anonymous_data_on_auth(
            uuid.uuid4(),
            "",
            session_service=session_service,
            video_task_service=video_task_service,
        )

        assert result.total == 0
        session_service.reassign_anonymous_to_user.assert_not_called()
        video_task_service.reassign_anonymous_to_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_anonymous_id_calls_migrate(self):
        """测试: 有匿名 ID 时触发迁移"""
        session_service = AsyncMock()
        video_task_service = AsyncMock()
        user_id = uuid.uuid4()
        anonymous_id = str(uuid.uuid4())
        session_service.reassign_anonymous_to_user.return_value = 1
        video_task_service.reassign_anonymous_to_user.return_value = 2

        result = await migrate_anonymous_data_on_auth(
            user_id,
            anonymous_id,
            session_service=session_service,
            video_task_service=video_task_service,
        )

        assert isinstance(result, MigrationResult)
        assert result.sessions == 1
        assert result.video_tasks == 2


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
        reassignment_service = AsyncMock()
        reassignment_service.migrate.return_value = MigrationResult(sessions=1, video_tasks=2)

        manager = UserManager(
            mock_user_db,
            anonymous_reassignment_service=reassignment_service,
        )

        with (
            patch(
                "domains.identity.infrastructure.user_manager."
                "provision_default_tenant_for_new_user",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_prov,
        ):
            await manager.on_after_login(user, request=request)

            reassignment_service.migrate.assert_awaited_once_with(user.id, anonymous_id)
            mock_prov.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_after_login_no_cookie_skips_migration(self):
        """测试: 无匿名 Cookie 时不触发迁移"""
        from domains.identity.infrastructure.user_manager import UserManager

        user = self._create_mock_user()
        request = self._create_mock_request(anonymous_cookie=None)

        mock_user_db = MagicMock()
        reassignment_service = AsyncMock()
        manager = UserManager(
            mock_user_db,
            anonymous_reassignment_service=reassignment_service,
        )

        with (
            patch(
                "domains.identity.infrastructure.user_manager."
                "provision_default_tenant_for_new_user",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_prov,
        ):
            await manager.on_after_login(user, request=request)

            reassignment_service.migrate.assert_not_called()
            mock_prov.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_after_login_no_request_skips_migration(self):
        """测试: 无 Request 时不触发迁移"""
        from domains.identity.infrastructure.user_manager import UserManager

        user = self._create_mock_user()
        mock_user_db = MagicMock()
        reassignment_service = AsyncMock()
        manager = UserManager(
            mock_user_db,
            anonymous_reassignment_service=reassignment_service,
        )

        with (
            patch(
                "domains.identity.infrastructure.user_manager."
                "provision_default_tenant_for_new_user",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_prov,
        ):
            await manager.on_after_login(user, request=None)

            reassignment_service.migrate.assert_not_called()
            mock_prov.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_after_register_triggers_migration(self):
        """测试: 注册后钩子也触发匿名数据迁移"""
        from domains.identity.infrastructure.user_manager import UserManager

        anonymous_id = str(uuid.uuid4())
        user = self._create_mock_user()
        request = self._create_mock_request(anonymous_cookie=anonymous_id)

        mock_user_db = MagicMock()
        mock_user_db.session = AsyncMock()
        reassignment_service = AsyncMock()
        reassignment_service.migrate.return_value = MigrationResult(sessions=2, video_tasks=0)

        manager = UserManager(
            mock_user_db,
            anonymous_reassignment_service=reassignment_service,
        )

        with (
            patch(
                "domains.identity.infrastructure.user_manager."
                "provision_default_tenant_for_new_user",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_prov,
        ):
            await manager.on_after_register(user, request=request)

            reassignment_service.migrate.assert_awaited_once_with(user.id, anonymous_id)
            mock_prov.assert_called_once()
