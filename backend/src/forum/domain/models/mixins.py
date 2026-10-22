from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column


class IDMixin:
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
    )


class TitleUniqueMixin:
    title: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )


class TitleNonUniqueMixin:
    title: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )


class DescriptionMixin:
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class PositionMixin:
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default='0',
    )


class IsActiveMixin:
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )


class MessageMixin:
    message: Mapped[str] = mapped_column(Text, nullable=False)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
    )


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
        onupdate=datetime.now,
    )
