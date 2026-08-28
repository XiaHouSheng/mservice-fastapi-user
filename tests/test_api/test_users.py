"""用户管理 API 集成测试。"""

import pytest


@pytest.mark.asyncio
async def test_get_me(client):
    """测试获取当前用户信息。"""
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Test@1234",
            "gender": "male",
        },
    )
    token = register_resp.json()["access_token"]
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client):
    """测试未认证访问 /me 失败。"""
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_me(client):
    """测试更新当前用户信息。"""
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Test@1234",
            "gender": "male",
        },
    )
    token = register_resp.json()["access_token"]
    response = await client.put(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Test User", "bio": "Hello World"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Test User"
    assert data["bio"] == "Hello World"


@pytest.mark.asyncio
async def test_change_password(client):
    """测试修改密码。"""
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Test@1234",
            "gender": "male",
        },
    )
    token = register_resp.json()["access_token"]
    response = await client.post(
        "/api/v1/users/me/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": "Test@1234", "new_password": "New@12345"},
    )
    assert response.status_code == 204

    # 用新密码登录
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "New@12345"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_me(client):
    """测试软删除用户。"""
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Test@1234",
            "gender": "male",
        },
    )
    token = register_resp.json()["access_token"]
    response = await client.delete(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    # 删除后无法登录
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "Test@1234"},
    )
    assert login_resp.status_code == 401
