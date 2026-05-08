"""
User Model Repository - 用户模型仓储
"""

from typing import Any
import uuid

from sqlalchemy import func, select

from domains.agent.infrastructure.models.user_model import UserModel
from libs.db.base_repository import OwnedRepositoryBase


class UserModelRepository(OwnedRepositoryBase[UserModel]):
    @property
    def model_class(self) -> type[UserModel]:
        return UserModel

    @property
    def anonymous_user_id_column(self) -> str:
        return "anonymous_user_id"

    async def create(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        display_name: str = "",
        provider: str = "",
        model_id: str = "",
        api_key_encrypted: str | None = None,
        api_base: str | None = None,
        model_types: list[str] | None = None,
        config: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> UserModel:
        model = UserModel(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            display_name=display_name,
            provider=provider,
            model_id=model_id,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            model_types=model_types or ["text"],
            config=config,
            is_active=is_active,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def update(self, entity_id: uuid.UUID, **kwargs: Any) -> UserModel | None:
        model = await self.get_owned(entity_id)
        if not model:
            return None
        allowed = {
            "display_name", "provider", "model_id", "api_key_encrypted",
            "api_base", "model_types", "config", "is_active",
        }
        for field, value in kwargs.items():
            if field in allowed and value is not None:
                setattr(model, field, value)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def find_by_type(
        self,
        model_type: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[UserModel]:
        """按模型类型查询（含所有权过滤）"""
        query = (
            select(UserModel)
            .where(UserModel.model_types.any(model_type))
            .where(UserModel.is_active.is_(True))
            .order_by(UserModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        query = self._apply_ownership_filter(query)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_by_type(self, model_type: str) -> int:
        """统计指定类型的活跃模型数量（含所有权过滤）"""
        query = (
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.model_types.any(model_type))
            .where(UserModel.is_active.is_(True))
        )
        query = self._apply_ownership_filter(query)
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def find_active(
        self,
        skip: int = 0,
        limit: int = 50,
    ) -> list[UserModel]:
        """查询当前用户的所有启用模型"""
        return await self.find_owned(
            skip=skip,
            limit=limit,
            is_active=True,
            order_by="created_at",
            order_desc=True,
        )
