"""Репозиторий тем форума."""

from datetime import datetime, timedelta
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forum.adapters.repositories.base import SQLAlchemyRepository
from forum.domain.models import Category, Post, Topic
from forum.service_layer.timeutils import utc_now_naive


class TopicRepository(SQLAlchemyRepository[Topic, int]):
    """Репозиторий тем форума."""

    def __init__(self, session: AsyncSession):
        super().__init__(Topic, session)

    async def list_filtered(
        self,
        *,
        category_id: int | None = None,
        is_topic: bool | None = None,
        is_active: bool = True,
    ) -> list[Topic]:
        """
        Список тем с фильтрами.

        Сортировка по position ASC.

        Args:
            category_id: фильтр по категории или None.
            is_topic: фильтр флага is_topic или None.
            is_active: фильтр активности (по умолчанию True).

        Returns:
            Список Topic, отсортированный по position.
        """
        stmt = select(Topic).where(Topic.is_active.is_(is_active))

        if category_id is not None:
            stmt = stmt.where(Topic.category_id == category_id)

        if is_topic is not None:
            stmt = stmt.where(Topic.is_topic.is_(is_topic))

        stmt = stmt.order_by(Topic.position.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_active_recent(
        self,
        *,
        days: int = 7,
        is_active: bool = True,
    ) -> list[Topic]:
        """
        Темы с последним активным сообщением за N дней.

        Сортировка: по времени последнего сообщения DESC.

        Args:
            days: окно активности в днях (по умолчанию 7).
            is_active: фильтр активности темы.

        Returns:
            Список Topic с недавней активностью.
        """
        cutoff = utc_now_naive() - timedelta(days=days)
        last_post_subq = (
            select(
                Post.topic_id.label('topic_id'),
                func.max(Post.created_at).label('last_at'),
            )
            .where(Post.is_active.is_(True))
            .group_by(Post.topic_id)
            .having(func.max(Post.created_at) >= cutoff)
            .subquery()
        )
        stmt = (
            select(Topic)
            .join(
                last_post_subq,
                Topic.id == last_post_subq.c.topic_id,
            )
            .where(Topic.is_active.is_(is_active))
            .order_by(last_post_subq.c.last_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_participated(
        self,
        user_uid: uuid.UUID,
        *,
        is_active: bool = True,
    ) -> list[Topic]:
        """
        Темы, где пользователь оставил хотя бы один пост.

        Сортировка по времени последнего сообщения DESC
        (nulls last).

        Args:
            user_uid: UUID автора постов.
            is_active: фильтр активности темы.

        Returns:
            Список Topic с участием пользователя.
        """
        last_post_subq = (
            select(
                Post.topic_id.label('topic_id'),
                func.max(Post.created_at).label('last_at'),
            )
            .where(Post.is_active.is_(True))
            .group_by(Post.topic_id)
            .subquery()
        )
        participated_ids = (
            select(Post.topic_id)
            .where(
                Post.author_id == user_uid,
                Post.is_active.is_(True),
            )
            .distinct()
            .subquery()
        )
        stmt = (
            select(Topic)
            .join(
                participated_ids,
                Topic.id == participated_ids.c.topic_id,
            )
            .outerjoin(
                last_post_subq,
                Topic.id == last_post_subq.c.topic_id,
            )
            .where(Topic.is_active.is_(is_active))
            .order_by(last_post_subq.c.last_at.desc().nullslast())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_by_category_and_title(
        self,
        category_id: int,
        title: str,
    ) -> Topic | None:
        """
        Тема с данным названием в категории.

        Статус is_active не фильтруется.

        Args:
            category_id: ID категории.
            title: точное название темы.

        Returns:
            Topic или None.
        """
        stmt = select(Topic).where(
            Topic.category_id == category_id,
            Topic.title == title,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_id(
        self,
        topic_id: int,
    ) -> Topic | None:
        """
        Активная тема с категорией, разделом и автором.

        Args:
            topic_id: ID темы.

        Returns:
            Topic со связями или None.
        """
        stmt = (
            select(Topic)
            .where(
                Topic.id == topic_id,
                Topic.is_active.is_(True),
            )
            .options(
                selectinload(Topic.category).selectinload(
                    Category.section,
                ),
                selectinload(Topic.author),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_posts_counts(
        self,
        topic_ids: list[int],
    ) -> dict[int, int]:
        """
        Число активных сообщений по id тем.

        Args:
            topic_ids: список ID тем.

        Returns:
            Словарь topic_id → число активных Post.
            Пустой dict при пустом topic_ids.
        """
        if not topic_ids:
            return {}

        stmt = (
            select(Post.topic_id, func.count(Post.id))
            .where(
                Post.topic_id.in_(topic_ids),
                Post.is_active.is_(True),
            )
            .group_by(Post.topic_id)
        )
        result = await self.session.execute(stmt)
        return {
            topic_id: count
            for topic_id, count in result.all()
        }

    async def count_by_author(
        self,
        author_id: uuid.UUID,
        *,
        is_active: bool = True,
    ) -> int:
        """
        Число тем, созданных автором.

        Args:
            author_id: UUID автора темы.
            is_active: фильтр активности.

        Returns:
            Количество Topic автора.
        """
        stmt = (
            select(func.count(Topic.id))
            .where(
                Topic.author_id == author_id,
                Topic.is_active.is_(is_active),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_last_posts(
        self,
        topic_ids: list[int],
    ) -> dict[int, Post]:
        """
        Последнее активное сообщение по каждой теме.

        Post загружается с author.

        Args:
            topic_ids: список ID тем.

        Returns:
            Словарь topic_id → последний Post.
            Пустой dict при пустом topic_ids.
        """
        if not topic_ids:
            return {}

        stmt = (
            select(Post)
            .where(
                Post.topic_id.in_(topic_ids),
                Post.is_active.is_(True),
            )
            .options(selectinload(Post.author))
            .distinct(Post.topic_id)
            .order_by(Post.topic_id, Post.created_at.desc())
        )
        result = await self.session.execute(stmt)
        posts = list(result.scalars().unique().all())
        return {post.topic_id: post for post in posts}

    async def get_last_created_at_by_author(
        self,
        author_id: uuid.UUID,
    ) -> datetime | None:
        """
        Время последней темы автора.

        Args:
            author_id: UUID автора.

        Returns:
            max(created_at) или None.
        """
        stmt = select(func.max(Topic.created_at)).where(
            Topic.author_id == author_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_author_since(
        self,
        author_id: uuid.UUID,
        since: datetime,
    ) -> int:
        """
        Число тем автора с момента since.

        Args:
            author_id: UUID автора.
            since: нижняя граница created_at.

        Returns:
            Количество Topic с created_at >= since.
        """
        stmt = select(func.count(Topic.id)).where(
            Topic.author_id == author_id,
            Topic.created_at >= since,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
