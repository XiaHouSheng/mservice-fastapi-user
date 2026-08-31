from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jose import JWTError, jwt
from jose.jwk import RSAKey
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.PASSWORD_BCRYPT_ROUNDS,
)


def _load_key(value: str) -> str:
    """解析 JWT 密钥：若值为 PEM 字符串则直接返回，否则视为文件路径读取。"""
    if value and "-----BEGIN" not in value:
        return Path(value).read_text(encoding="utf-8")
    return value


# RS256 非对称：私钥仅用于签发（保留在 user-service），公钥用于校验（可对外分发）
_private_key = _load_key(settings.JWT_PRIVATE_KEY)
_public_key = _load_key(settings.JWT_PUBLIC_KEY)


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希。"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希值是否匹配。"""
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(
    subject: str,
    user_id: int,
    service_name: str,
    expires_delta: timedelta,
    token_type: str,
) -> str:
    """使用私钥生成 JWT 令牌。"""
    expire = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "user_id": user_id,
        "service_name": service_name,
        "type": token_type,
        "exp": expire,
    }
    return jwt.encode(payload, _private_key, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, user_id: int, service_name: str) -> str:
    """生成访问令牌（默认 30 分钟）。"""
    return _create_token(
        subject=subject,
        user_id=user_id,
        service_name=service_name,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )


def create_refresh_token(subject: str, user_id: int, service_name: str) -> str:
    """生成刷新令牌（默认 7 天）。"""
    return _create_token(
        subject=subject,
        user_id=user_id,
        service_name=service_name,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )


def decode_token(token: str) -> dict[str, Any]:
    """使用公钥解码并校验 JWT，失败抛出 JWTError。"""
    return jwt.decode(token, _public_key, algorithms=[settings.ALGORITHM])


def get_jwks() -> dict[str, Any]:
    """以 JWK 集合形式返回公钥，供其他服务通过 /.well-known/jwks.json 获取并验证令牌。"""
    rsa_key: RSAKey = RSAKey(_public_key.encode("utf-8"), algorithm=settings.ALGORITHM)
    return {"keys": [rsa_key.to_dict()]}


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_jwks",
    "JWTError",
]
