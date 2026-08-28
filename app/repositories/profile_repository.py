"""通用扩展表 Repository。

每个业务的扩展表模型不同，但 CRUD 逻辑一致，因此用泛型方式统一处理。
传入 profile_model 类即可操作对应扩展表。
"""

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class ProfileRepository(Generic[T]):
    """通用扩展表数据访问层。

    用法::

        repo = ProfileRepository(db, ForumProfile)
        profile = await repo.get_by_user_id(user_id)
        await repo.create(user_id, {"level": 5, "points": 100})
        await repo.update(user_id, {"points": 200})
    """

    def __init__(self, db: AsyncSession, profile_model: type[T]) -> None:
        self.db = db
        self.profile_model = profile_model

    async def get_by_user_id(self, user_id: int) -> T | None:
        """根据 user_id 获取扩展表记录。"""
        stmt = select(self.profile_model).where(self.profile_model.user_id == user_id)  # type: ignore[attr-defined]
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_id: int, data: dict[str, Any] | None = None) -> T:
        """创建扩展表记录。"""
        profile = self.profile_model(user_id=user_id, **(data or {}))  # type: ignore[call-arg]
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def get_or_create(self, user_id: int, data: dict[str, Any] | None = None) -> T:
        """获取扩展表记录，不存在则创建。"""
        profile = await self.get_by_user_id(user_id)
        if profile is None:
            profile = await self.create(user_id, data)
        return profile

    async def update(self, user_id: int, data: dict[str, Any]) -> T | None:
        """更新扩展表记录。"""
        profile = await self.get_by_user_id(user_id)
        if profile is None:
            return None
        for field, value in data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        profile.updated_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def upsert(self, user_id: int, data: dict[str, Any]) -> T:
        """存在则更新，不存在则创建。"""
        profile = await self.get_by_user_id(user_id)
        if profile is None:
            return await self.create(user_id, data)
        for field, value in data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        profile.updated_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]
        await self.db.flush()
        await self.db.refresh(profile)
        return profile
