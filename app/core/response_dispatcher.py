"""微服务响应分发器。

根据用户的 service_name，从注册机中取出对应的响应构建器，
传入用户对象和业务扩展表记录，返回该微服务专属格式的响应。
未注册的 service_name 回退到 default。
"""

from typing import Any

from app.core.service_registry import registry
from app.models.user import User
from app.schemas.user import UserResponse


class ResponseDispatcher:
    """微服务响应分发器。"""

    def __init__(self, registry_instance=registry) -> None:
        self.registry = registry_instance

    def dispatch(self, user: User, profile: Any = None) -> Any:
        """根据 user.service_name 分发到对应服务的响应构建器。

        Args:
            user: 用户对象
            profile: 业务扩展表记录（无扩展表时为 None）

        Returns:
            该微服务专属格式的响应（dict 或 Pydantic 模型）
        """
        descriptor = self.registry.get(user.service_name)
        if descriptor is None or descriptor.response_builder is None:
            descriptor = self.registry.get("default")

        builder = descriptor.response_builder if descriptor is not None else None
        if builder is None:
            return UserResponse.model_validate(user)
        return builder(user, profile)

    def dispatch_list(self, users: list[tuple[User, Any | None]]) -> list[Any]:
        """批量分发用户列表。

        Args:
            users: (user, profile) 元组列表
        """
        return [self.dispatch(user, profile) for user, profile in users]


# 全局分发器实例
dispatcher = ResponseDispatcher()
