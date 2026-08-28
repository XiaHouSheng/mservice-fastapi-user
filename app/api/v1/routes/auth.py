from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.token import RefreshTokenRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse, status_code=201, summary="用户注册")
async def register(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """注册新用户并返回 JWT 令牌。"""
    auth_service = AuthService(db)
    return await auth_service.register(user_data)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """使用用户名（或邮箱）和密码登录，返回 JWT 令牌。"""
    auth_service = AuthService(db)
    return await auth_service.login(username=form_data.username, password=form_data.password)


@router.post("/refresh", response_model=TokenResponse, summary="刷新访问令牌")
async def refresh_token(
    data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """使用刷新令牌换取新的访问令牌。"""
    auth_service = AuthService(db)
    return await auth_service.refresh(data.refresh_token)


@router.post("/logout", status_code=204, summary="用户登出")
async def logout() -> None:
    """用户登出（无状态 JWT，客户端丢弃令牌即可）。"""
    return None
