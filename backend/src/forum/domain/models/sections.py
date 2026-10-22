from typing import TYPE_CHECKING

from sqlalchemy import Boolean, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forum.domain.models.base import Base
from forum.domain.models.mixins import (
    CreatedAtMixin,
    IDMixin,
    IsActiveMixin,
    PositionMixin,
    TitleUniqueMixin,
    UpdatedAtMixin,
)


if TYPE_CHECKING:
    from forum.domain.models.categories import Category


class Section(
    IDMixin,
    TitleUniqueMixin,
    PositionMixin,
    IsActiveMixin,
    CreatedAtMixin,
    UpdatedAtMixin,
    Base,
):
    """
    Раздел форума (верхний уровень на главной).

    is_topic=True — специальный раздел.
    Без описания: только название.
    """

    is_topic: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    categories: Mapped[list['Category']] = relationship(
        back_populates='section',
        cascade='all, delete-orphan',
        order_by='Category.position',
    )

    def __str__(self) -> str:
        return self.title
