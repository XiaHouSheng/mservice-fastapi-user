from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.proxy.log_proxy import LogProxy
from app.repositories.user_repository import UserRepository
from app.schemas.token import TokenResponse
from app.schemas.user import UserCreate
from app.services.user_service import UserService


class AuthService:
    """认证业务逻辑层。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo: UserRepository = LogProxy(UserRepository(db))
        self.user_service = UserService(db)

    async def register(self, user_data: UserCreate) -> TokenResponse:
        """用户注册，成功后直接返回令牌。"""
        user = await self.user_service.create_user(user_data)
        return self._issue_tokens(user)

    async def login(self, username: str, password: str) -> TokenResponse:
        """用户登录（用户名或邮箱）。"""
        user = await self.repo.get_by_username(username)
        if user is None:
            user = await self.repo.get_by_email(username)

        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if user.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账户已被删除",
            )

        await self.repo.update_last_login(user)
        return self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """使用刷新令牌换取新的访问令牌。"""
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌无效或已过期",
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌类型错误",
            )

        user_id = payload.get("user_id")
        user = await self.repo.get_by_id(user_id)
        if user is None or user.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )
        return self._issue_tokens(user)

    @staticmethod
    def _issue_tokens(user: User) -> TokenResponse:
        """为用户签发访问令牌和刷新令牌。"""
        access_token = create_access_token(
            subject=user.username,
            user_id=user.id,
            role=user.role.value,
        )
        refresh_token = create_refresh_token(
            subject=user.username,
            user_id=user.id,
            role=user.role.value,
        )
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
