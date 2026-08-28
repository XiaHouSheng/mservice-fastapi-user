from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, get_current_admin_user
from app.models.enums import UserStatus
from app.models.user import User
from app.schemas.user import (
    UserChangePassword,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """获取当前登录用户的详细信息。"""
    return current_user


@router.put("/me", response_model=UserResponse, summary="更新当前用户信息")
async def update_me(
    user_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """更新当前登录用户的个人信息。"""
    user_service = UserService(db)
    return await user_service.update_user(current_user.id, user_data)


@router.post("/me/change-password", status_code=204, summary="修改当前用户密码")
async def change_password(
    data: UserChangePassword,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """修改当前登录用户的密码。"""
    user_service = UserService(db)
    await user_service.change_password(current_user.id, data)


@router.delete("/me", status_code=204, summary="删除当前用户（软删除）")
async def delete_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """软删除当前登录用户账户。"""
    user_service = UserService(db)
    await user_service.delete_user(current_user.id)


@router.get("/{user_id}", response_model=UserResponse, summary="获取指定用户信息")
async def get_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """根据用户 ID 获取用户详细信息。"""
    user_service = UserService(db)
    return await user_service.get_user_by_id(user_id)


@router.get("", response_model=UserListResponse, summary="获取用户列表（管理员）")
async def list_users(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(20, ge=1, le=100, description="每页条数"),
    status_filter: UserStatus | None = Query(None, description="按状态筛选"),
) -> UserListResponse:
    """分页获取用户列表，仅管理员可访问。"""
    user_service = UserService(db)
    users, total = await user_service.list_users(skip=skip, limit=limit, status_filter=status_filter)
    return UserListResponse(total=total, items=[UserResponse.model_validate(u) for u in users])
