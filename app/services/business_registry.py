"""业务注册主入口。

所有微服务的扩展表模型、扩展字段校验模型和响应构建器统一在此注册。
新增业务时：
  1. 在 app/models/extensions/ 下创建扩展表模型（继承 BaseProfile）
  2. 定义该服务的扩展字段校验 Pydantic 模型（可选）
  3. 实现响应构建函数 (user: User, profile: ProfileModel | None) -> dict | BaseModel
  4. 在 setup_services() 中添加一行 registry.register(...)
"""

from typing import Any

from pydantic import BaseModel

from app.core.service_registry import registry
from app.models.extensions.forum import ForumProfile
from app.models.extensions.shop import ShopProfile
from app.models.user import User
from app.schemas.user import UserResponse

# ---------------------------------------------------------------------------
# 默认服务
# ---------------------------------------------------------------------------

def _default_response_builder(user: User, profile: Any = None) -> UserResponse:
    """默认服务：返回基础 UserResponse。"""
    return UserResponse.model_validate(user)

def setup_services() -> None:
    """注册所有业务微服务。在应用启动时调用。

    后续新增业务在此函数内添加注册代码即可。
    """
    # default 服务（基础响应，始终注册）
    if not registry.has("default"):
        registry.register(
            name="default",
            description="默认服务，返回基础用户信息",
            response_builder=_default_response_builder,
        )

    # ------------------------------------------------------------------
    # 在此注册新的业务微服务
    # 示例：
    #   registry.register(
    #       name="your_service",
    #       description="你的服务描述",
    #       profile_model=YourProfile,        # app/models/extensions/your.py
    #       extension_model=YourExtension,    # 可选，API 入参校验
    #       response_builder=build_your_response,
    #   )
    # ------------------------------------------------------------------
