"""部署引导：按 .env 配置自动创建超级用户。"""

import logging

from sqlalchemy import or_, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User

logger = logging.getLogger(__name__)

# 常见弱口令（统一小写比较），命中则拒绝自动创建
_WEAK_PASSWORDS = {
    "password",
    "123456",
    "12345678",
    "123456789",
    "admin",
    "admin123",
    "root",
    "superuser",
    "superadmin",
}


def _is_weak_password(password: str, username: str) -> bool:
    """判断密码强度是否不足，弱口令拒绝自动创建。"""
    if len(password) < 8:
        return True
    if password.lower() in _WEAK_PASSWORDS:
        return True
    if password.lower() == username.lower():
        return True
    return False


async def ensure_superuser(db) -> bool:
    """确保超级用户存在（幂等）。返回是否新建。

    规则：
    - SUPERUSER_PASSWORD 为空 → 跳过创建（部署方未启用该能力）；
    - 密码强度不足 → 拒绝创建（避免默认弱口令风险）；
    - 用户名或邮箱已存在（含软删除）→ 跳过，不重置密码、不修改角色。
    """
    username = settings.SUPERUSER_USERNAME.strip()
    password = settings.SUPERUSER_PASSWORD

    if not username or not password:
        logger.warning("未配置 SUPERUSER_USERNAME/SUPERUSER_PASSWORD，跳过超级用户自动创建")
        return False

    if _is_weak_password(password, username):
        logger.warning("超级用户密码强度不足，拒绝自动创建（请配置强 SUPERUSER_PASSWORD）")
        return False

    # 已存在（含软删除）则跳过：不重置密码、不修改角色
    stmt = select(User).where(
        or_(User.username == username, User.email == settings.SUPERUSER_EMAIL)
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing is not None:
        logger.info("超级用户 %s 已存在，跳过创建", username)
        return False

    user = User(
        username=username,
        email=settings.SUPERUSER_EMAIL,
        hashed_password=hash_password(password),
        full_name=settings.SUPERUSER_FULL_NAME,
        service_name=settings.SUPERUSER_SERVICE_NAME,
        role="superuser",
    )
    db.add(user)
    await db.flush()
    logger.info(
        "已自动创建超级用户: %s (service=%s, role=superuser)",
        username,
        settings.SUPERUSER_SERVICE_NAME,
    )
    return True


async def init_superuser() -> bool:
    """应用启动时调用：在独立会话内自动创建超级用户并提交。"""
    async with AsyncSessionLocal() as session:
        try:
            result = await ensure_superuser(session)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
