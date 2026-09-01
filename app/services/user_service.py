from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.proxy.log_proxy import LogProxy
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserChangePassword, UserCreate, UserUpdate
from app.core.security import hash_password, verify_password


class UserService:
    """用户业务逻辑层。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo: UserRepository = LogProxy(UserRepository(db))  # type: ignore[assignment]

    async def create_user(self, user_data: UserCreate) -> User:
        """创建新用户（注册）。"""
        existing = await self.repo.get_by_username_or_email(user_data.username, user_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名或邮箱已被注册",
            )

        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            full_name=user_data.full_name,
            service_name=user_data.service_name,
        )
        return await self.repo.create(user)

    async def get_user_by_id(self, user_id: int) -> User:
        """根据 ID 获取用户。"""
        user = await self.repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )
        return user

    async def update_user(self, user_id: int, user_data: UserUpdate) -> User:
        """更新用户信息。"""
        user = await self.get_user_by_id(user_id)

        update_data = user_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        if update_data:
            user = await self.repo.update(user)

        return user

    async def change_password(self, user_id: int, data: UserChangePassword) -> User:
        """修改用户密码。"""
        user = await self.get_user_by_id(user_id)
        if not verify_password(data.old_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="原密码错误",
            )
        if data.old_password == data.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新密码不能与原密码相同",
            )
        new_hash = hash_password(data.new_password)
        return await self.repo.change_password(user, new_hash)

    async def delete_user(self, user_id: int) -> None:
        """软删除用户。"""
        user = await self.get_user_by_id(user_id)
        await self.repo.soft_delete(user)

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        service_name: str | None = None,
    ) -> tuple[list[User], int]:
        """分页获取用户列表。"""
        return await self.repo.list_users(skip=skip, limit=limit, service_name=service_name)
