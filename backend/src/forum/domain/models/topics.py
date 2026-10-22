from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forum.domain.models.base import Base
from forum.domain.models.mixins import (
    CreatedAtMixin,
    DescriptionMixin,
    IDMixin,
    IsActiveMixin,
    PositionMixin,
    TitleNonUniqueMixin,
    UpdatedAtMixin,
)


if TYPE_CHECKING:
    from forum.domain.models.categories import Category
    from forum.domain.models.content_acl import TopicUserAccess
    from forum.domain.models.posts import Post
    from forum.domain.models.users import User


class Topic(
    IDMixin,
    TitleNonUniqueMixin,
    DescriptionMixin,
    PositionMixin,
    IsActiveMixin,
    CreatedAtMixin,
    UpdatedAtMixin,
    Base,
):
    """
    Тема внутри категории.

    Пара category + title уникальна.
    is_topic=True — тема для блока «Специальные разделы».
    """

    __table_args__ = (
        UniqueConstraint(
            'category_id',
            'title',
            name='uq_topic_category_id_title',
        ),
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey('category.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey('user.uid', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    is_topic: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    is_closed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    is_restricted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    views_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default='0',
    )

    category: Mapped['Category'] = relationship(
        back_populates='topics',
    )
    author: Mapped['User'] = relationship(
        back_populates='topics',
        foreign_keys=[author_id],
    )
    posts: Mapped[list['Post']] = relationship(
        back_populates='topic',
        cascade='all, delete-orphan',
        order_by='Post.created_at',
    )
    access_rows: Mapped[list['TopicUserAccess']] = (
        relationship(
            back_populates='topic',
            cascade='all, delete-orphan',
        )
    )
    allowed_users: Mapped[list['User']] = relationship(
        secondary='topic_user_access',
        viewonly=False,
        overlaps='access_rows,topic,topic_access_rows,user',
    )

    def __str__(self) -> str:
        return self.title
