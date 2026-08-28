from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserStatus
from app.models.user import User


class UserRepository:
    """用户数据访问层，封装所有 CRUD 操作。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user: User) -> User:
        """创建新用户。"""
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        """根据 ID 获取用户（含软删除过滤）。"""
        stmt = select(User).where(User.id == user_id, User.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """根据用户名获取用户。"""
        stmt = select(User).where(User.username == username, User.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """根据邮箱获取用户。"""
        stmt = select(User).where(User.email == email, User.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username_or_email(self, username: str, email: str) -> User | None:
        """检查用户名或邮箱是否已存在。"""
        stmt = select(User).where(
            (User.username == username) | (User.email == email),
            User.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, user: User) -> User:
        """更新用户信息。"""
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_last_login(self, user: User) -> User:
        """更新最后登录时间。"""
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()
        return user

    async def soft_delete(self, user: User) -> User:
        """软删除用户。"""
        user.is_deleted = True
        user.status = UserStatus.DELETED
        user.deleted_at = datetime.now(timezone.utc)
        user.is_active = False
        await self.db.flush()
        return user

    async def change_password(self, user: User, hashed_password: str) -> User:
        """修改密码。"""
        user.hashed_password = hashed_password
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return user

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        status: UserStatus | None = None,
    ) -> tuple[list[User], int]:
        """分页获取用户列表，返回 (用户列表, 总数)。"""
        base_where = [User.is_deleted.is_(False)]
        if status is not None:
            base_where.append(User.status == status)

        count_stmt = select(func.count()).select_from(User).where(*base_where)
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = (
            select(User)
            .where(*base_where)
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        users = list(result.scalars().all())
        return users, total
