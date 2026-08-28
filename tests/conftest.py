"""Pytest 共享 fixtures。"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import Base, engine
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """每个测试前重建数据库表。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """提供异步测试客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
