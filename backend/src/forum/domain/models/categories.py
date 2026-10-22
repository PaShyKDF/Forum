from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forum.domain.models.base import Base
from forum.domain.models.mixins import (
    CreatedAtMixin,
    DescriptionMixin,
    IDMixin,
    IsActiveMixin,
    PositionMixin,
    TitleUniqueMixin,
    UpdatedAtMixin,
)


if TYPE_CHECKING:
    from forum.domain.models.content_acl import (
        CategoryUserAccess,
    )
    from forum.domain.models.sections import Section
    from forum.domain.models.topics import Topic
    from forum.domain.models.users import User


class Category(
    IDMixin,
    TitleUniqueMixin,
    DescriptionMixin,
    PositionMixin,
    IsActiveMixin,
    CreatedAtMixin,
    UpdatedAtMixin,
    Base,
):
    """Категория внутри раздела форума."""

    # nullable до backfill в ensure_default_section
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey('section.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    is_restricted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    section: Mapped['Section'] = relationship(
        back_populates='categories',
        foreign_keys=[section_id],
    )
    topics: Mapped[list['Topic']] = relationship(
        back_populates='category',
        cascade='all, delete-orphan',
        order_by='Topic.position',
    )
    access_rows: Mapped[list['CategoryUserAccess']] = (
        relationship(
            back_populates='category',
            cascade='all, delete-orphan',
        )
    )
    # M2M для SQLAdmin / удобного выбора пользователей
    allowed_users: Mapped[list['User']] = relationship(
        secondary='category_user_access',
        viewonly=False,
        overlaps='access_rows,category,category_access_rows,user',
    )

    def __str__(self) -> str:
        return self.title
