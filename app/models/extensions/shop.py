"""商城服务扩展表。"""

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.extensions.base import BaseProfile


class ShopProfile(BaseProfile):
    __tablename__ = "user_shop_profiles"

    member_level: Mapped[str] = mapped_column(String(30), default="普通会员", nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    coupons: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
