"""论坛服务扩展表。"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.extensions.base import BaseProfile


class ForumProfile(BaseProfile):
    __tablename__ = "user_forum_profiles"

    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(50), default="新手上路", nullable=False)
