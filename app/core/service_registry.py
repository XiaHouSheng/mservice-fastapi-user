"""微服务注册机。

以 service_name 为 key，注册每个微服务的扩展表模型、扩展字段校验模型和响应构建器。
新服务接入时只需调用 registry.register() 或使用 @registry.service() 装饰器。
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase

from app.models.user import User
from app.schemas.user import UserResponse

# 响应构建器签名：接收 User 对象和扩展表对象（无扩展表时为 None），返回该服务专属响应
ResponseBuilder = Callable[[User, Any], Any]

# 扩展表 ORM 模型类
ProfileModel = type[DeclarativeBase]


@dataclass
class ServiceDescriptor:
    """微服务描述符。"""

    name: str
    description: str = ""
    # 该服务的扩展表 ORM 模型类（如 ForumProfile），用于分表存储业务字段
    profile_model: ProfileModel | None = None
    # 该服务的扩展字段校验模型（Pydantic Model 类），用于 API 入参校验
    extension_model: type[BaseModel] | None = None
    # 响应构建函数
    response_builder: ResponseBuilder | None = None
    # 额外元数据
    metadata: dict[str, Any] = field(default_factory=dict)


class ServiceRegistry:
    """微服务注册机。

    用法::

        registry = ServiceRegistry()

        # 方式一：直接注册
        registry.register(
            name="forum",
            description="论坛服务",
            profile_model=ForumProfile,
            extension_model=ForumExtension,
            response_builder=build_forum_response,
        )

        # 方式二：装饰器
        @registry.service("shop", description="商城服务", profile_model=ShopProfile)
        def build_shop_response(user: User, profile: ShopProfile | None) -> dict:
            return {...}
    """

    def __init__(self) -> None:
        self._services: dict[str, ServiceDescriptor] = {}

    def register(
        self,
        name: str,
        description: str = "",
        profile_model: ProfileModel | None = None,
        extension_model: type[BaseModel] | None = None,
        response_builder: ResponseBuilder | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ServiceDescriptor:
        """注册一个微服务。"""
        if name in self._services:
            raise ValueError(f"微服务 '{name}' 已注册")
        descriptor = ServiceDescriptor(
            name=name,
            description=description,
            profile_model=profile_model,
            extension_model=extension_model,
            response_builder=response_builder,
            metadata=metadata or {},
        )
        self._services[name] = descriptor
        return descriptor

    def service(
        self,
        name: str,
        description: str = "",
        profile_model: ProfileModel | None = None,
        extension_model: type[BaseModel] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Callable[[ResponseBuilder], ResponseBuilder]:
        """装饰器方式注册响应构建器。"""

        def decorator(builder: ResponseBuilder) -> ResponseBuilder:
            self.register(
                name=name,
                description=description,
                profile_model=profile_model,
                extension_model=extension_model,
                response_builder=builder,
                metadata=metadata,
            )
            return builder

        return decorator

    def get(self, name: str) -> ServiceDescriptor | None:
        """获取微服务描述符，不存在返回 None。"""
        return self._services.get(name)

    def has(self, name: str) -> bool:
        """检查微服务是否已注册。"""
        return name in self._services

    def list_services(self) -> list[ServiceDescriptor]:
        """列出所有已注册的微服务。"""
        return list(self._services.values())

    def unregister(self, name: str) -> None:
        """注销微服务。"""
        self._services.pop(name, None)


def _default_response_builder(user: User, profile: Any = None) -> UserResponse:
    """默认服务：返回基础 UserResponse。"""
    return UserResponse.model_validate(user)


# 全局注册机实例
registry = ServiceRegistry()

# 注册默认服务
registry.register(
    name="default",
    description="默认服务，返回基础用户信息",
    response_builder=_default_response_builder,
)
