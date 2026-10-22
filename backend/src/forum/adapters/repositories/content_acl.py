"""Репозиторий ACL категорий и тем."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from forum.domain.models import User
from forum.domain.models.content_acl import (
    CategoryUserAccess,
    TopicUserAccess,
)


class ContentAclRepository:
    """Whitelist пользователей для скрытых сущностей."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def user_has_category_access(
        self,
        category_id: int,
        user_uid: uuid.UUID,
    ) -> bool:
        """
        Проверяет доступ пользователя к скрытой категории.

        Ищет запись в CategoryUserAccess по паре
        category_id + user_uid.

        Args:
            category_id: ID категории.
            user_uid: UUID пользователя.

        Returns:
            True, если пользователь в whitelist категории.
        """
        stmt = select(CategoryUserAccess.user_uid).where(
            CategoryUserAccess.category_id == category_id,
            CategoryUserAccess.user_uid == user_uid,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def user_has_topic_access(
        self,
        topic_id: int,
        user_uid: uuid.UUID,
    ) -> bool:
        """
        Проверяет доступ пользователя к скрытой теме.

        Ищет запись в TopicUserAccess по паре
        topic_id + user_uid.

        Args:
            topic_id: ID темы.
            user_uid: UUID пользователя.

        Returns:
            True, если пользователь в whitelist темы.
        """
        stmt = select(TopicUserAccess.user_uid).where(
            TopicUserAccess.topic_id == topic_id,
            TopicUserAccess.user_uid == user_uid,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def user_has_any_topic_access_in_category(
        self,
        category_id: int,
        user_uid: uuid.UUID,
    ) -> bool:
        """
        Есть ли у пользователя доступ хотя бы к одной теме
        в данной категории.

        Используется для косвенного доступа к категории
        через whitelist тем.

        Args:
            category_id: ID категории.
            user_uid: UUID пользователя.

        Returns:
            True, если есть TopicUserAccess к теме категории.
        """
        from forum.domain.models import Topic

        stmt = (
            select(TopicUserAccess.user_uid)
            .join(Topic, Topic.id == TopicUserAccess.topic_id)
            .where(
                Topic.category_id == category_id,
                TopicUserAccess.user_uid == user_uid,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_category_users(
        self,
        category_id: int,
    ) -> list[User]:
        """
        Пользователи whitelist скрытой категории.

        Сортировка по display_name по возрастанию.

        Args:
            category_id: ID категории.

        Returns:
            Список User из CategoryUserAccess.
        """
        stmt = (
            select(User)
            .join(
                CategoryUserAccess,
                CategoryUserAccess.user_uid == User.uid,
            )
            .where(
                CategoryUserAccess.category_id == category_id,
            )
            .order_by(User.display_name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_topic_users(
        self,
        topic_id: int,
    ) -> list[User]:
        """
        Пользователи whitelist скрытой темы.

        Сортировка по display_name по возрастанию.

        Args:
            topic_id: ID темы.

        Returns:
            Список User из TopicUserAccess.
        """
        stmt = (
            select(User)
            .join(
                TopicUserAccess,
                TopicUserAccess.user_uid == User.uid,
            )
            .where(TopicUserAccess.topic_id == topic_id)
            .order_by(User.display_name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_category_user_ids(
        self,
        category_id: int,
    ) -> list[uuid.UUID]:
        """
        UUID пользователей whitelist категории.

        Args:
            category_id: ID категории.

        Returns:
            Список user_uid из CategoryUserAccess.
        """
        stmt = select(CategoryUserAccess.user_uid).where(
            CategoryUserAccess.category_id == category_id,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_topic_user_ids(
        self,
        topic_id: int,
    ) -> list[uuid.UUID]:
        """
        UUID пользователей whitelist темы.

        Args:
            topic_id: ID темы.

        Returns:
            Список user_uid из TopicUserAccess.
        """
        stmt = select(TopicUserAccess.user_uid).where(
            TopicUserAccess.topic_id == topic_id,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def set_category_users(
        self,
        category_id: int,
        user_uids: list[uuid.UUID],
    ) -> None:
        """
        Полностью заменяет whitelist категории.

        Удаляет старые записи CategoryUserAccess и создаёт
        новые по уникальным uid (порядок сохраняется).

        Args:
            category_id: ID категории.
            user_uids: новый список UUID пользователей.
        """
        await self.session.execute(
            delete(CategoryUserAccess).where(
                CategoryUserAccess.category_id == category_id,
            ),
        )
        unique_uids = list(dict.fromkeys(user_uids))
        for uid in unique_uids:
            self.session.add(
                CategoryUserAccess(
                    category_id=category_id,
                    user_uid=uid,
                ),
            )
        await self.session.flush()

    async def set_topic_users(
        self,
        topic_id: int,
        user_uids: list[uuid.UUID],
    ) -> None:
        """
        Полностью заменяет whitelist темы.

        Удаляет старые записи TopicUserAccess и создаёт
        новые по уникальным uid (порядок сохраняется).

        Args:
            topic_id: ID темы.
            user_uids: новый список UUID пользователей.
        """
        await self.session.execute(
            delete(TopicUserAccess).where(
                TopicUserAccess.topic_id == topic_id,
            ),
        )
        unique_uids = list(dict.fromkeys(user_uids))
        for uid in unique_uids:
            self.session.add(
                TopicUserAccess(
                    topic_id=topic_id,
                    user_uid=uid,
                ),
            )
        await self.session.flush()

    async def category_ids_with_user_access(
        self,
        user_uid: uuid.UUID,
    ) -> set[int]:
        """
        ID категорий, где пользователь в whitelist.

        Args:
            user_uid: UUID пользователя.

        Returns:
            Множество category_id из CategoryUserAccess.
        """
        stmt = select(CategoryUserAccess.category_id).where(
            CategoryUserAccess.user_uid == user_uid,
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def topic_ids_with_user_access(
        self,
        user_uid: uuid.UUID,
    ) -> set[int]:
        """
        ID тем, где пользователь в whitelist.

        Args:
            user_uid: UUID пользователя.

        Returns:
            Множество topic_id из TopicUserAccess.
        """
        stmt = select(TopicUserAccess.topic_id).where(
            TopicUserAccess.user_uid == user_uid,
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def category_ids_via_topic_access(
        self,
        user_uid: uuid.UUID,
    ) -> set[int]:
        """
        ID категорий, доступных через whitelist тем.

        Берёт distinct category_id у тем, к которым
        у пользователя есть TopicUserAccess.

        Args:
            user_uid: UUID пользователя.

        Returns:
            Множество category_id через доступ к темам.
        """
        from forum.domain.models import Topic

        stmt = (
            select(Topic.category_id)
            .join(
                TopicUserAccess,
                TopicUserAccess.topic_id == Topic.id,
            )
            .where(TopicUserAccess.user_uid == user_uid)
            .distinct()
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())
