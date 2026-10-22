"""Репозиторий сообщений (постов) форума."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forum.adapters.repositories.base import SQLAlchemyRepository
from forum.domain.models import Post


def _post_load_options():
    """Автор поста и цитируемое сообщение с автором."""
    return (
        selectinload(Post.author),
        selectinload(Post.quoted_post).selectinload(
            Post.author,
        ),
    )


class PostRepository(SQLAlchemyRepository[Post, int]):
    """Репозиторий сообщений форума."""

    def __init__(self, session: AsyncSession):
        super().__init__(Post, session)

    async def list_by_topic(
        self,
        topic_id: int,
        *,
        is_active: bool = True,
        newest_first: bool = True,
    ) -> list[Post]:
        """
        Сообщения темы с авторами и цитатами.

        По умолчанию от новых к старым (created_at DESC).

        Args:
            topic_id: ID темы.
            is_active: фильтр активности (по умолчанию True).
            newest_first: DESC по created_at, иначе ASC.

        Returns:
            Список Post с подгруженными связями.
        """
        stmt = (
            select(Post)
            .where(
                Post.topic_id == topic_id,
                Post.is_active.is_(is_active),
            )
            .options(*_post_load_options())
        )

        if newest_first:
            stmt = stmt.order_by(Post.created_at.desc())
        else:
            stmt = stmt.order_by(Post.created_at.asc())

        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_active_by_id(
        self,
        post_id: int,
    ) -> Post | None:
        """
        Активное сообщение с автором и цитатой.

        Args:
            post_id: ID сообщения.

        Returns:
            Post или None, если нет / неактивен.
        """
        stmt = (
            select(Post)
            .where(
                Post.id == post_id,
                Post.is_active.is_(True),
            )
            .options(*_post_load_options())
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_roots(
        self,
        topic_id: int,
        *,
        is_active: bool = True,
    ) -> int:
        """
        Число корневых сообщений темы.

        Корневые — без reply_to_post_id.

        Args:
            topic_id: ID темы.
            is_active: фильтр активности.

        Returns:
            Количество корневых Post.
        """
        stmt = (
            select(func.count(Post.id))
            .where(
                Post.topic_id == topic_id,
                Post.reply_to_post_id.is_(None),
                Post.is_active.is_(is_active),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def list_roots(
        self,
        topic_id: int,
        *,
        limit: int,
        offset: int,
        is_active: bool = True,
    ) -> list[Post]:
        """
        Корневые сообщения темы (новые сверху).

        Args:
            topic_id: ID темы.
            limit: размер страницы.
            offset: смещение пагинации.
            is_active: фильтр активности.

        Returns:
            Страница корневых Post с связями.
        """
        stmt = (
            select(Post)
            .where(
                Post.topic_id == topic_id,
                Post.reply_to_post_id.is_(None),
                Post.is_active.is_(is_active),
            )
            .options(*_post_load_options())
            .order_by(Post.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count_by_author(
        self,
        author_id: uuid.UUID,
        *,
        is_active: bool = True,
    ) -> int:
        """
        Число сообщений автора.

        Args:
            author_id: UUID автора.
            is_active: фильтр активности.

        Returns:
            Количество Post автора.
        """
        stmt = (
            select(func.count(Post.id))
            .where(
                Post.author_id == author_id,
                Post.is_active.is_(is_active),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_replies(
        self,
        parent_post_id: int,
        *,
        is_active: bool = True,
    ) -> int:
        """
        Число прямых ответов на сообщение.

        Args:
            parent_post_id: ID родительского Post.
            is_active: фильтр активности.

        Returns:
            Количество прямых ответов.
        """
        stmt = (
            select(func.count(Post.id))
            .where(
                Post.reply_to_post_id == parent_post_id,
                Post.is_active.is_(is_active),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_replies_counts(
        self,
        parent_ids: list[int],
        *,
        is_active: bool = True,
    ) -> dict[int, int]:
        """
        Счётчики прямых ответов для списка родителей.

        Args:
            parent_ids: ID родительских сообщений.
            is_active: фильтр активности.

        Returns:
            Словарь parent_id → число ответов.
            Пустой dict при пустом parent_ids.
        """
        if not parent_ids:
            return {}

        stmt = (
            select(
                Post.reply_to_post_id,
                func.count(Post.id),
            )
            .where(
                Post.reply_to_post_id.in_(parent_ids),
                Post.is_active.is_(is_active),
            )
            .group_by(Post.reply_to_post_id)
        )
        result = await self.session.execute(stmt)
        return {
            parent_id: count
            for parent_id, count in result.all()
            if parent_id is not None
        }

    async def list_replies(
        self,
        parent_post_id: int,
        *,
        limit: int,
        offset: int,
        is_active: bool = True,
    ) -> list[Post]:
        """
        Прямые ответы на сообщение (новые сверху).

        Args:
            parent_post_id: ID родительского Post.
            limit: размер страницы.
            offset: смещение пагинации.
            is_active: фильтр активности.

        Returns:
            Страница ответов с связями.
        """
        stmt = (
            select(Post)
            .where(
                Post.reply_to_post_id == parent_post_id,
                Post.is_active.is_(is_active),
            )
            .options(*_post_load_options())
            .order_by(Post.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_last_created_at_by_author(
        self,
        author_id: uuid.UUID,
    ) -> datetime | None:
        """
        Время последнего сообщения автора.

        Args:
            author_id: UUID автора.

        Returns:
            max(created_at) или None.
        """
        stmt = select(func.max(Post.created_at)).where(
            Post.author_id == author_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_author_since(
        self,
        author_id: uuid.UUID,
        since: datetime,
    ) -> int:
        """
        Число сообщений автора с момента since.

        Args:
            author_id: UUID автора.
            since: нижняя граница created_at.

        Returns:
            Количество Post с created_at >= since.
        """
        stmt = select(func.count(Post.id)).where(
            Post.author_id == author_id,
            Post.created_at >= since,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def count_newer_roots(
        self,
        topic_id: int,
        created_at: datetime,
        *,
        is_active: bool = True,
    ) -> int:
        """
        Число корневых сообщений новее указанного времени.

        Args:
            topic_id: ID темы.
            created_at: граница (строго больше).
            is_active: фильтр активности.

        Returns:
            Количество корневых Post с created_at > границы.
        """
        stmt = select(func.count(Post.id)).where(
            Post.topic_id == topic_id,
            Post.reply_to_post_id.is_(None),
            Post.is_active.is_(is_active),
            Post.created_at > created_at,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_newer_replies(
        self,
        parent_post_id: int,
        created_at: datetime,
        *,
        is_active: bool = True,
    ) -> int:
        """
        Число ответов новее указанного времени.

        Args:
            parent_post_id: ID родительского Post.
            created_at: граница (строго больше).
            is_active: фильтр активности.

        Returns:
            Количество ответов с created_at > границы.
        """
        stmt = select(func.count(Post.id)).where(
            Post.reply_to_post_id == parent_post_id,
            Post.is_active.is_(is_active),
            Post.created_at > created_at,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)
