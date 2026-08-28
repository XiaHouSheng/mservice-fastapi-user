"""微服务注册机与响应分发器单元测试。"""

from datetime import datetime
from typing import Any

import pytest
from pydantic import BaseModel

from app.core.response_dispatcher import ResponseDispatcher
from app.core.service_registry import ServiceRegistry
from app.models.user import User


# ---------------------------------------------------------------------------
# 测试用扩展模型 & 构建器
# ---------------------------------------------------------------------------

class ForumExtension(BaseModel):
    level: int = 1
    points: int = 0
    title: str = "新手上路"


class ShopExtension(BaseModel):
    member_level: str = "普通会员"
    balance: float = 0.0
    coupons: int = 0


def build_forum_response(user: User, profile: Any = None) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "service_name": user.service_name,
        "forum": ForumExtension().model_dump(),
    }


def build_shop_response(user: User, profile: Any = None) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "service_name": user.service_name,
        "shop": ShopExtension().model_dump(),
    }


def _make_user(user_id: int = 1, service_name: str = "default") -> User:
    return User(
        id=user_id,
        username=f"user{user_id}",
        email=f"user{user_id}@example.com",
        hashed_password="hashed",
        full_name="Test User",
        service_name=service_name,
        created_at=datetime.now(),
    )


# ---------------------------------------------------------------------------
# 注册机测试
# ---------------------------------------------------------------------------

class TestServiceRegistry:
    def test_register_and_get(self):
        reg = ServiceRegistry()
        reg.register(
            name="forum",
            description="论坛服务",
            extension_model=ForumExtension,
            response_builder=build_forum_response,
        )
        descriptor = reg.get("forum")
        assert descriptor is not None
        assert descriptor.name == "forum"
        assert descriptor.description == "论坛服务"
        assert descriptor.extension_model is ForumExtension
        assert descriptor.response_builder is build_forum_response

    def test_register_duplicate_raises(self):
        reg = ServiceRegistry()
        reg.register(name="forum", response_builder=build_forum_response)
        with pytest.raises(ValueError, match="已注册"):
            reg.register(name="forum", response_builder=build_forum_response)

    def test_get_nonexistent_returns_none(self):
        reg = ServiceRegistry()
        assert reg.get("nonexistent") is None

    def test_has(self):
        reg = ServiceRegistry()
        assert not reg.has("forum")
        reg.register(name="forum", response_builder=build_forum_response)
        assert reg.has("forum")

    def test_list_services(self):
        reg = ServiceRegistry()
        reg.register(name="forum", response_builder=build_forum_response)
        reg.register(name="shop", response_builder=build_shop_response)
        services = reg.list_services()
        assert len(services) == 2
        names = {s.name for s in services}
        assert names == {"forum", "shop"}

    def test_decorator_registration(self):
        reg = ServiceRegistry()

        @reg.service("shop", description="商城服务", extension_model=ShopExtension)
        def shop_builder(user: User, profile: Any = None) -> dict:
            return {"id": user.id}

        descriptor = reg.get("shop")
        assert descriptor is not None
        assert descriptor.description == "商城服务"
        assert descriptor.extension_model is ShopExtension
        assert descriptor.response_builder is shop_builder

    def test_unregister(self):
        reg = ServiceRegistry()
        reg.register(name="forum", response_builder=build_forum_response)
        assert reg.has("forum")
        reg.unregister("forum")
        assert not reg.has("forum")


# ---------------------------------------------------------------------------
# 分发器测试
# ---------------------------------------------------------------------------

class TestResponseDispatcher:
    def test_dispatch_default(self):
        reg = ServiceRegistry()
        reg.register(name="default", response_builder=lambda u, p: {"default": True, "id": u.id})
        dispatcher = ResponseDispatcher(reg)
        user = _make_user(service_name="default")
        result = dispatcher.dispatch(user)
        assert result["default"] is True
        assert result["id"] == 1

    def test_dispatch_forum(self):
        reg = ServiceRegistry()
        reg.register(name="forum", response_builder=build_forum_response)
        dispatcher = ResponseDispatcher(reg)
        user = _make_user(service_name="forum")
        result = dispatcher.dispatch(user)
        assert result["service_name"] == "forum"
        assert "forum" in result
        assert result["forum"]["level"] == 1
        assert result["forum"]["points"] == 0

    def test_dispatch_shop(self):
        reg = ServiceRegistry()
        reg.register(name="shop", response_builder=build_shop_response)
        dispatcher = ResponseDispatcher(reg)
        user = _make_user(service_name="shop")
        result = dispatcher.dispatch(user)
        assert result["service_name"] == "shop"
        assert "shop" in result
        assert result["shop"]["member_level"] == "普通会员"
        assert result["shop"]["balance"] == 0.0

    def test_dispatch_with_profile(self):
        """测试传入 profile 对象时构建器能读取扩展字段。"""
        reg = ServiceRegistry()

        def builder(user: User, profile: Any = None) -> dict:
            return {
                "id": user.id,
                "custom_field": profile.custom_field if profile else "default",
            }

        reg.register(name="custom", response_builder=builder)
        dispatcher = ResponseDispatcher(reg)
        user = _make_user(service_name="custom")

        # 不传 profile
        result = dispatcher.dispatch(user)
        assert result["custom_field"] == "default"

        # 传 profile
        class FakeProfile:
            custom_field = "from_profile"
        result = dispatcher.dispatch(user, FakeProfile())
        assert result["custom_field"] == "from_profile"

    def test_dispatch_unknown_service_fallback_to_default(self):
        reg = ServiceRegistry()
        reg.register(name="default", response_builder=lambda u, p: {"fallback": True})
        dispatcher = ResponseDispatcher(reg)
        user = _make_user(service_name="unknown_service")
        result = dispatcher.dispatch(user)
        assert result["fallback"] is True

    def test_dispatch_list(self):
        reg = ServiceRegistry()
        reg.register(name="forum", response_builder=build_forum_response)
        reg.register(name="shop", response_builder=build_shop_response)
        dispatcher = ResponseDispatcher(reg)
        users = [
            (_make_user(user_id=1, service_name="forum"), None),
            (_make_user(user_id=2, service_name="shop"), None),
        ]
        results = dispatcher.dispatch_list(users)
        assert len(results) == 2
        assert results[0]["service_name"] == "forum"
        assert results[1]["service_name"] == "shop"
        assert "forum" in results[0]
        assert "shop" in results[1]
