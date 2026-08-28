from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.response_dispatcher import dispatcher
from app.models.user import User
from app.schemas.user import UserChangePassword, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("/me", summary="获取当前用户信息（按 service_name 分发响应）")
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """获取当前登录用户信息，根据 service_name 返回对应微服务格式的响应。"""
    user_service = UserService(db)
    _, profile = await user_service.get_user_with_profile(current_user.id)
    return dispatcher.dispatch(current_user, profile)


@router.put("/me", summary="更新当前用户信息")
async def update_me(
    user_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """更新当前登录用户的个人信息及业务扩展字段。"""
    user_service = UserService(db)
    updated = await user_service.update_user(current_user.id, user_data)
    profile = await user_service.get_user_profile(updated)
    return dispatcher.dispatch(updated, profile)


@router.post("/me/change-password", status_code=204, summary="修改当前用户密码")
async def change_password(
    data: UserChangePassword,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """修改当前登录用户的密码。"""
    user_service = UserService(db)
    await user_service.change_password(current_user.id, data)


@router.delete("/me", status_code=204, summary="删除当前用户（软删除）")
async def delete_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """软删除当前登录用户账户。"""
    user_service = UserService(db)
    await user_service.delete_user(current_user.id)


@router.get("/{user_id}", summary="获取指定用户信息（按 service_name 分发响应）")
async def get_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """根据用户 ID 获取用户信息，根据 service_name 返回对应微服务格式的响应。"""
    user_service = UserService(db)
    user, profile = await user_service.get_user_with_profile(user_id)
    return dispatcher.dispatch(user, profile)


@router.get("", summary="获取用户列表（按 service_name 筛选，批量分发响应）")
async def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(20, ge=1, le=100, description="每页条数"),
    service_name: str | None = Query(None, description="按微服务名筛选"),
) -> dict[str, Any]:
    """分页获取用户列表，每个用户按其 service_name 返回对应格式的响应。"""
    user_service = UserService(db)
    users, total = await user_service.list_users(skip=skip, limit=limit, service_name=service_name)
    # 批量获取每个用户的扩展记录
    items_with_profile: list[tuple[User, Any | None]] = []
    for user in users:
        profile = await user_service.get_user_profile(user)
        items_with_profile.append((user, profile))
    return {"total": total, "items": dispatcher.dispatch_list(items_with_profile)}
