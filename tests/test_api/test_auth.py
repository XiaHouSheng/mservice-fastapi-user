"""认证 API 集成测试。"""

import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    """测试用户注册成功。"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Test@1234",
            "gender": "male",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    """测试重复用户名注册失败。"""
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "Test@1234",
        "gender": "male",
    }
    await client.post("/api/v1/auth/register", json=user_data)
    response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    """测试用户登录成功。"""
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Test@1234",
            "gender": "male",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "Test@1234"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """测试错误密码登录失败。"""
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Test@1234",
            "gender": "male",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "Wrong@1234"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client):
    """测试刷新令牌。"""
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Test@1234",
            "gender": "male",
        },
    )
    refresh_token = register_resp.json()["refresh_token"]
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
