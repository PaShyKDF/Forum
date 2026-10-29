"""Модель ежедневных просмотров тем."""

from datetime import date, datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forum.domain.models.base import Base
from forum.domain.models.mixins import IDMixin


if TYPE_CHECKING:
    from forum.domain.models.topics import Topic
    from forum.domain.models.users import User


class TopicView(IDMixin, Base):
    """
    Один просмотр темы зрителем за московские сутки.

    viewer_key: u:<uid> или a:<anon_id>.
    Уникальность (topic_id, viewer_key, view_date)
    даёт правило «1 зритель = 1 просмотр в день».
    """

    __tablename__ = 'topic_view'
    __table_args__ = (
        UniqueConstraint(
            'topic_id',
            'viewer_key',
            'view_date',
            name='uq_topic_view_topic_viewer_date',
        ),
        Index(
            'ix_topic_view_date_viewer',
            'view_date',
            'viewer_key',
        ),
    )

    topic_id: Mapped[int] = mapped_column(
        ForeignKey('topic.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    viewer_key: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey('user.uid', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    anon_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    view_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    topic: Mapped['Topic'] = relationship()
    user: Mapped['User | None'] = relationship()

    def __str__(self) -> str:
        return (
            f'topic={self.topic_id} '
            f'{self.viewer_key} {self.view_date}'
        )
