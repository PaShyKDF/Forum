"""Репозиторий категорий форума."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forum.adapters.repositories.base import SQLAlchemyRepository
from forum.domain.models import Category, Post, Topic


class CategoryRepository(SQLAlchemyRepository[Category, int]):
    """Репозиторий категорий форума."""

    def __init__(self, session: AsyncSession):
        super().__init__(Category, session)

    async def list_filtered(
        self,
        *,
        section_id: int | None = None,
        is_active: bool = True,
    ) -> list[Category]:
        """
        Список категорий с фильтром и сортировкой.

        Сортировка по position ASC; section подгружается.

        Args:
            section_id: фильтр по разделу или None.
            is_active: фильтр активности (по умолчанию True).

        Returns:
            Список Category с section.
        """
        stmt = (
            select(Category)
            .where(Category.is_active.is_(is_active))
            .options(selectinload(Category.section))
        )
        if section_id is not None:
            stmt = stmt.where(Category.section_id == section_id)
        stmt = stmt.order_by(Category.position.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_active_by_id(
        self,
        category_id: int,
    ) -> Category | None:
        """
        Активная категория по ID (с разделом).

        Args:
            category_id: ID категории.

        Returns:
            Category с section или None.
        """
        stmt = (
            select(Category)
            .where(
                Category.id == category_id,
                Category.is_active.is_(True),
            )
            .options(selectinload(Category.section))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_title(
        self,
        title: str,
    ) -> Category | None:
        """
        Категория по точному названию.

        Статус is_active не фильтруется.

        Args:
            title: точное название категории.

        Returns:
            Category или None.
        """
        stmt = select(Category).where(Category.title == title)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_max_position(
        self,
        section_id: int,
    ) -> int:
        """
        Максимальный position в разделе.

        Args:
            section_id: ID раздела.

        Returns:
            max(position) или -1, если категорий нет.
        """
        stmt = select(
            func.coalesce(func.max(Category.position), -1),
        ).where(Category.section_id == section_id)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def assign_null_to_section(
        self,
        section_id: int,
    ) -> int:
        """
        Привязывает категории без раздела к указанному.

        Args:
            section_id: ID раздела-назначения.

        Returns:
            Число обновлённых строк.
        """
        stmt = (
            update(Category)
            .where(Category.section_id.is_(None))
            .values(section_id=section_id)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(result.rowcount or 0)

    async def get_topics_counts(
        self,
        category_ids: list[int],
        *,
        exclude_restricted: bool = False,
    ) -> dict[int, int]:
        """
        Число активных тем по id категорий.

        Args:
            category_ids: список ID категорий.
            exclude_restricted: исключить is_restricted
                темы.

        Returns:
            Словарь category_id → число тем.
            Пустой dict при пустом category_ids.
        """
        if not category_ids:
            return {}

        conditions = [
            Topic.category_id.in_(category_ids),
            Topic.is_active.is_(True),
        ]
        if exclude_restricted:
            conditions.append(
                Topic.is_restricted.is_(False),
            )

        stmt = (
            select(Topic.category_id, func.count(Topic.id))
            .where(*conditions)
            .group_by(Topic.category_id)
        )
        result = await self.session.execute(stmt)
        return {
            category_id: count
            for category_id, count in result.all()
        }

    async def get_posts_counts(
        self,
        category_ids: list[int],
        *,
        exclude_restricted: bool = False,
    ) -> dict[int, int]:
        """
        Число активных сообщений по id категорий.

        Args:
            category_ids: список ID категорий.
            exclude_restricted: исключить is_restricted
                темы.

        Returns:
            Словарь category_id → число Post.
            Пустой dict при пустом category_ids.
        """
        if not category_ids:
            return {}

        conditions = [
            Topic.category_id.in_(category_ids),
            Topic.is_active.is_(True),
            Post.is_active.is_(True),
        ]
        if exclude_restricted:
            conditions.append(
                Topic.is_restricted.is_(False),
            )

        stmt = (
            select(
                Topic.category_id,
                func.count(Post.id),
            )
            .join(Post, Post.topic_id == Topic.id)
            .where(*conditions)
            .group_by(Topic.category_id)
        )
        result = await self.session.execute(stmt)
        return {
            category_id: count
            for category_id, count in result.all()
        }

    async def get_last_posts(
        self,
        category_ids: list[int],
        *,
        exclude_restricted: bool = False,
    ) -> dict[int, Post]:
        """
        Последнее активное сообщение по каждой категории.

        Post загружается с author и topic (для title).

        Args:
            category_ids: список ID категорий.
            exclude_restricted: исключить is_restricted
                темы.

        Returns:
            Словарь category_id → последний Post.
            Пустой dict при пустом category_ids.
        """
        if not category_ids:
            return {}

        conditions = [
            Topic.category_id.in_(category_ids),
            Topic.is_active.is_(True),
            Post.is_active.is_(True),
        ]
        if exclude_restricted:
            conditions.append(
                Topic.is_restricted.is_(False),
            )

        stmt = (
            select(Post)
            .join(Topic, Post.topic_id == Topic.id)
            .where(*conditions)
            .options(
                selectinload(Post.author),
                selectinload(Post.topic),
            )
            .distinct(Topic.category_id)
            .order_by(
                Topic.category_id,
                Post.created_at.desc(),
            )
        )
        result = await self.session.execute(stmt)
        posts = list(result.scalars().unique().all())
        return {
            post.topic.category_id: post
            for post in posts
            if post.topic is not None
        }
