"""Модель обращений в техническую поддержку."""

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forum.domain.models.base import Base
from forum.domain.models.mixins import (
    CreatedAtMixin,
    IDMixin,
    IsActiveMixin,
    UpdatedAtMixin,
)


if TYPE_CHECKING:
    from forum.domain.models.users import User


class SupportTicket(
    IDMixin,
    IsActiveMixin,
    CreatedAtMixin,
    UpdatedAtMixin,
    Base,
):
    """Обращение в техническую поддержку."""

    __table_args__ = (
        Index(
            'ix_supportticket_user_created',
            'user_id',
            'created_at',
        ),
        Index(
            'ix_supportticket_email_created',
            'email',
            'created_at',
        ),
        Index(
            'ix_supportticket_ip_created',
            'client_ip',
            'created_at',
        ),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey('user.uid', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default='new',
        server_default='new',
        index=True,
    )
    client_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        index=True,
    )

    user: Mapped['User | None'] = relationship(
        foreign_keys=[user_id],
    )

    def __str__(self) -> str:
        return f'#{self.id} {self.subject}'
