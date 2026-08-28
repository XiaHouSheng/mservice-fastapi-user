"""业务扩展表基类。

每个业务一张扩展表，通过 user_id 外键关联主表 users。
新增业务时继承 BaseProfile 并定义专属字段即可。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BaseProfile(Base):
    """扩展表抽象基类。

    所有业务扩展表都继承此类，自动获得 user_id 外键和时间戳。
    子类需定义 __tablename__ 和业务专属字段。
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
