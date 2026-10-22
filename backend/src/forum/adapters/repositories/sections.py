"""Репозиторий разделов форума."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forum.adapters.repositories.base import SQLAlchemyRepository
from forum.domain.models import Section


class SectionRepository(SQLAlchemyRepository[Section, int]):
    """Репозиторий разделов форума."""

    def __init__(self, session: AsyncSession):
        super().__init__(Section, session)

    async def list_filtered(
        self,
        *,
        is_topic: bool | None = None,
        is_active: bool = True,
    ) -> list[Section]:
        """
        Список разделов с фильтром и сортировкой.

        Сортировка по position ASC.

        Args:
            is_topic: фильтр флага is_topic или None.
            is_active: фильтр активности (по умолчанию True).

        Returns:
            Список Section, отсортированный по position.
        """
        stmt = select(Section).where(
            Section.is_active.is_(is_active),
        )
        if is_topic is not None:
            stmt = stmt.where(Section.is_topic.is_(is_topic))
        stmt = stmt.order_by(Section.position.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_active_by_id(
        self,
        section_id: int,
    ) -> Section | None:
        """
        Активный раздел по ID.

        Args:
            section_id: ID раздела.

        Returns:
            Section или None.
        """
        stmt = select(Section).where(
            Section.id == section_id,
            Section.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_title(
        self,
        title: str,
    ) -> Section | None:
        """
        Раздел по точному названию.

        Args:
            title: точное название раздела.

        Returns:
            Section или None.
        """
        stmt = select(Section).where(Section.title == title)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
