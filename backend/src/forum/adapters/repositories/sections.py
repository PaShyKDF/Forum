"""Репозиторий разделов форума."""

from sqlalchemy import func, select, update
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

    async def list_scale(
        self,
        *,
        is_topic: bool,
    ) -> list[Section]:
        """
        Все разделы шкалы (включая неактивные).

        Сортировка по position ASC. Статус is_active
        не фильтруется.

        Args:
            is_topic: True — спецразделы, False — обычные.

        Returns:
            Список Section шкалы по position.
        """
        stmt = (
            select(Section)
            .where(Section.is_topic.is_(is_topic))
            .order_by(Section.position.asc())
        )
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

    async def get_by_position(
        self,
        *,
        is_topic: bool,
        position: int,
    ) -> Section | None:
        """
        Раздел шкалы с точной позицией.

        Args:
            is_topic: шкала (спец / обычные).
            position: искомый position.

        Returns:
            Section или None, если слот свободен.
        """
        stmt = select(Section).where(
            Section.is_topic.is_(is_topic),
            Section.position == position,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_max_position(
        self,
        *,
        is_topic: bool,
    ) -> int:
        """
        Максимальный position в шкале.

        Args:
            is_topic: шкала (спец / обычные).

        Returns:
            max(position) или 0, если разделов нет.
        """
        stmt = select(
            func.coalesce(func.max(Section.position), 0),
        ).where(Section.is_topic.is_(is_topic))
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def list_from_position(
        self,
        *,
        is_topic: bool,
        position: int,
    ) -> list[Section]:
        """
        Разделы шкалы с position >= указанного.

        Args:
            is_topic: шкала (спец / обычные).
            position: нижняя граница включительно.

        Returns:
            Список Section по position ASC.
        """
        stmt = (
            select(Section)
            .where(
                Section.is_topic.is_(is_topic),
                Section.position >= position,
            )
            .order_by(Section.position.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def shift_positions_up(
        self,
        *,
        is_topic: bool,
        from_position: int,
        exclude_id: int | None = None,
    ) -> None:
        """
        Сдвигает position на +1 для записей >= from.

        Args:
            is_topic: шкала (спец / обычные).
            from_position: начиная с какой позиции.
            exclude_id: ID раздела, который не сдвигать.
        """
        stmt = (
            update(Section)
            .where(
                Section.is_topic.is_(is_topic),
                Section.position >= from_position,
            )
            .values(position=Section.position + 1)
        )
        if exclude_id is not None:
            stmt = stmt.where(Section.id != exclude_id)
        await self.session.execute(stmt)
        await self.session.flush()

    async def shift_positions_down(
        self,
        *,
        is_topic: bool,
        after_position: int,
        exclude_id: int | None = None,
    ) -> None:
        """
        Сдвигает position на -1 для записей > after.

        Args:
            is_topic: шкала (спец / обычные).
            after_position: позиции строго больше этой.
            exclude_id: ID раздела, который не сдвигать.
        """
        stmt = (
            update(Section)
            .where(
                Section.is_topic.is_(is_topic),
                Section.position > after_position,
            )
            .values(position=Section.position - 1)
        )
        if exclude_id is not None:
            stmt = stmt.where(Section.id != exclude_id)
        await self.session.execute(stmt)
        await self.session.flush()
