"""Модель уведомлений о ответах и цитатах в темах."""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forum.domain.models.base import Base
from forum.domain.models.mixins import (
    CreatedAtMixin,
    IDMixin,
    IsActiveMixin,
    UpdatedAtMixin,
)


if TYPE_CHECKING:
    from forum.domain.models.posts import Post
    from forum.domain.models.topics import Topic
    from forum.domain.models.users import User


class TopicNotification(
    IDMixin,
    IsActiveMixin,
    CreatedAtMixin,
    UpdatedAtMixin,
    Base,
):
    """
    Уведомление о ответе или цитате на сообщение пользователя.

    read_at is None — ещё не открыто.
    is_active=False — удалено пользователем из списка.
    """

    __table_args__ = (
        Index(
            'ix_topicnotification_recipient_unread',
            'recipient_id',
            'is_active',
            'read_at',
        ),
    )

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('user.uid', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('user.uid', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey('topic.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    # Новое сообщение, на которое ведёт уведомление
    post_id: Mapped[int] = mapped_column(
        ForeignKey('post.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    # Исходное сообщение получателя (на которое ответили/цитировали)
    source_post_id: Mapped[int] = mapped_column(
        ForeignKey('post.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    # reply | quote
    kind: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )

    recipient: Mapped['User'] = relationship(
        foreign_keys=[recipient_id],
    )
    actor: Mapped['User'] = relationship(
        foreign_keys=[actor_id],
    )
    topic: Mapped['Topic'] = relationship(
        foreign_keys=[topic_id],
    )
    post: Mapped['Post'] = relationship(
        foreign_keys=[post_id],
    )
    source_post: Mapped['Post'] = relationship(
        foreign_keys=[source_post_id],
    )

    def __str__(self) -> str:
        return (
            f'TopicNotification(id={self.id}, '
            f'kind={self.kind}, post_id={self.post_id})'
        )
