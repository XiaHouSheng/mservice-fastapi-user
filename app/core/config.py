from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置，从环境变量 / .env 加载。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用
    APP_NAME: str = "User Service"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # 服务
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 数据库 (SQLite)
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/user_service.db"
    DATABASE_ECHO: bool = False

    # JWT（RS256 非对称加密：私钥签发，公钥校验）
    # 值可以是 PEM 字符串，也可以是 PEM 文件路径（security.py 自动识别并读取）
    JWT_PRIVATE_KEY: str = "keys/jwt_private.pem"
    JWT_PUBLIC_KEY: str = "keys/jwt_public.pem"
    ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 密码
    PASSWORD_BCRYPT_ROUNDS: int = 12

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/user_service.log"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 5

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # 日志操作类型
    LOG_OPERATIONS: List[str] = [
        "user_create",
        "user_update",
        "user_delete",
        "user_login",
        "user_logout",
        "password_change",
        "user_status_change",
        "role_change",
    ]

    @field_validator("ALLOWED_ORIGINS", "LOG_OPERATIONS", mode="before")
    @classmethod
    def _parse_list(cls, v):
        """支持从 .env 读取 JSON 数组字符串。"""
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [item.strip() for item in v.split(",") if item.strip()]
        return v


settings = Settings()
