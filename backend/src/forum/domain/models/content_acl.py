"""ACL: доступ пользователей к скрытым категориям и темам."""

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forum.domain.models.base import Base


if TYPE_CHECKING:
    from forum.domain.models.categories import Category
    from forum.domain.models.topics import Topic
    from forum.domain.models.users import User


class CategoryUserAccess(Base):
    """Допуск пользователя к скрытой категории."""

    __tablename__ = 'category_user_access'
    __table_args__ = (
        PrimaryKeyConstraint(
            'category_id',
            'user_uid',
            name='pk_category_user_access',
        ),
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey('category.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    user_uid: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('user.uid', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    category: Mapped['Category'] = relationship(
        back_populates='access_rows',
        foreign_keys=[category_id],
    )
    user: Mapped['User'] = relationship(
        back_populates='category_access_rows',
        foreign_keys=[user_uid],
    )


class TopicUserAccess(Base):
    """Допуск пользователя к скрытой теме."""

    __tablename__ = 'topic_user_access'
    __table_args__ = (
        PrimaryKeyConstraint(
            'topic_id',
            'user_uid',
            name='pk_topic_user_access',
        ),
    )

    topic_id: Mapped[int] = mapped_column(
        ForeignKey('topic.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    user_uid: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('user.uid', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    topic: Mapped['Topic'] = relationship(
        back_populates='access_rows',
        foreign_keys=[topic_id],
    )
    user: Mapped['User'] = relationship(
        back_populates='topic_access_rows',
        foreign_keys=[user_uid],
    )
