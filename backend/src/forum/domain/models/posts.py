from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, ForeignKey, Text, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forum.domain.models.base import Base
from forum.domain.models.mixins import (
    CreatedAtMixin,
    IDMixin,
    IsActiveMixin,
    UpdatedAtMixin,
)


if TYPE_CHECKING:
    from forum.domain.models.topics import Topic
    from forum.domain.models.users import User


class Post(
    IDMixin,
    IsActiveMixin,
    CreatedAtMixin,
    UpdatedAtMixin,
    Base,
):
    """Сообщение внутри темы."""

    topic_id: Mapped[int] = mapped_column(
        ForeignKey('topic.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('user.uid', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    # Ответ на корневое сообщение (только 1 уровень)
    reply_to_post_id: Mapped[int | None] = mapped_column(
        ForeignKey('post.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    # Цитата другого сообщения (не создаёт вложенность)
    quoted_post_id: Mapped[int | None] = mapped_column(
        ForeignKey('post.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    is_topic_starter: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    topic: Mapped['Topic'] = relationship(
        back_populates='posts',
        foreign_keys=[topic_id],
    )
    author: Mapped['User'] = relationship(
        back_populates='posts',
        foreign_keys=[author_id],
    )
    reply_to: Mapped['Post | None'] = relationship(
        back_populates='replies',
        remote_side='Post.id',
        foreign_keys=[reply_to_post_id],
    )
    replies: Mapped[list['Post']] = relationship(
        back_populates='reply_to',
        foreign_keys=[reply_to_post_id],
    )
    quoted_post: Mapped['Post | None'] = relationship(
        remote_side='Post.id',
        foreign_keys=[quoted_post_id],
    )

    def __str__(self) -> str:
        return f'Post(id={self.id}, topic_id={self.topic_id})'
