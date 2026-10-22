"""Репозиторий уведомлений о ответах и цитатах."""

from datetime import datetime
import uuid

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forum.adapters.repositories.base import SQLAlchemyRepository
from forum.domain.models import TopicNotification


def _notification_load_options():
    return (
        selectinload(TopicNotification.actor),
        selectinload(TopicNotification.topic),
        selectinload(TopicNotification.post),
        selectinload(TopicNotification.source_post),
    )


class TopicNotificationRepository(
    SQLAlchemyRepository[TopicNotification, int],
):
    """CRUD и выборки непрочитанных уведомлений."""

    def __init__(self, session: AsyncSession):
        super().__init__(TopicNotification, session)

    async def create_notification(
        self,
        *,
        recipient_id: uuid.UUID,
        actor_id: uuid.UUID,
        topic_id: int,
        post_id: int,
        source_post_id: int,
        kind: str,
    ) -> TopicNotification:
        """
        Создаёт уведомление о ответе или цитате.

        Args:
            recipient_id: UUID получателя.
            actor_id: UUID автора действия.
            topic_id: ID темы.
            post_id: ID нового сообщения.
            source_post_id: ID исходного (отвеченного/
                процитированного) сообщения.
            kind: тип уведомления (reply, quote и т.п.).

        Returns:
            Сохранённый TopicNotification.
        """
        notification = TopicNotification(
            recipient_id=recipient_id,
            actor_id=actor_id,
            topic_id=topic_id,
            post_id=post_id,
            source_post_id=source_post_id,
            kind=kind,
        )
        return await self.add(notification)

    async def list_active_unread(
        self,
        recipient_id: uuid.UUID,
        *,
        limit: int = 50,
    ) -> list[TopicNotification]:
        """
        Активные непрочитанные уведомления.

        Сортировка: новые сверху (created_at DESC).

        Args:
            recipient_id: UUID получателя.
            limit: максимум записей (по умолчанию 50).

        Returns:
            Список TopicNotification со связями.
        """
        stmt = (
            select(TopicNotification)
            .where(
                TopicNotification.recipient_id == recipient_id,
                TopicNotification.is_active.is_(True),
                TopicNotification.read_at.is_(None),
            )
            .options(*_notification_load_options())
            .order_by(TopicNotification.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count_active_unread(
        self,
        recipient_id: uuid.UUID,
    ) -> int:
        """
        Число активных непрочитанных уведомлений.

        Args:
            recipient_id: UUID получателя.

        Returns:
            Количество непрочитанных активных записей.
        """
        stmt = select(func.count(TopicNotification.id)).where(
            TopicNotification.recipient_id == recipient_id,
            TopicNotification.is_active.is_(True),
            TopicNotification.read_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_for_recipient(
        self,
        notification_id: int,
        recipient_id: uuid.UUID,
    ) -> TopicNotification | None:
        """
        Активное уведомление текущего получателя.

        Args:
            notification_id: ID уведомления.
            recipient_id: UUID ожидаемого получателя.

        Returns:
            TopicNotification со связями или None.
        """
        stmt = (
            select(TopicNotification)
            .where(
                TopicNotification.id == notification_id,
                TopicNotification.recipient_id == recipient_id,
                TopicNotification.is_active.is_(True),
            )
            .options(*_notification_load_options())
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_read(
        self,
        notification_id: int,
        recipient_id: uuid.UUID,
        *,
        read_at: datetime,
    ) -> TopicNotification | None:
        """
        Помечает уведомление прочитанным.

        Если read_at уже задан, повторно не меняет.

        Args:
            notification_id: ID уведомления.
            recipient_id: UUID получателя.
            read_at: время прочтения.

        Returns:
            Уведомление или None, если не найдено.
        """
        notification = await self.get_for_recipient(
            notification_id,
            recipient_id,
        )
        if notification is None:
            return None
        if notification.read_at is None:
            notification.read_at = read_at
            await self.session.flush()
        return notification

    async def dismiss(
        self,
        notification_id: int,
        recipient_id: uuid.UUID,
    ) -> bool:
        """
        Скрывает одно уведомление из списка.

        Ставит is_active=False (мягкое скрытие).

        Args:
            notification_id: ID уведомления.
            recipient_id: UUID получателя.

        Returns:
            True, если уведомление найдено и скрыто.
        """
        notification = await self.get_for_recipient(
            notification_id,
            recipient_id,
        )
        if notification is None:
            return False
        notification.is_active = False
        await self.session.flush()
        return True

    async def clear_all(
        self,
        recipient_id: uuid.UUID,
    ) -> int:
        """
        Скрывает все активные непрочитанные уведомления.

        Args:
            recipient_id: UUID получателя.

        Returns:
            Число обновлённых строк.
        """
        stmt = (
            update(TopicNotification)
            .where(
                TopicNotification.recipient_id == recipient_id,
                TopicNotification.is_active.is_(True),
                TopicNotification.read_at.is_(None),
            )
            .values(is_active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(result.rowcount or 0)

    async def delete_inactive_batch(
        self,
        *,
        limit: int = 500,
    ) -> int:
        """
        Физически удаляет пачку неактивных/прочитанных
        уведомлений.

        Выбирает до limit id, где is_active=False или
        read_at задан, и удаляет их.

        Args:
            limit: размер пачки (по умолчанию 500).

        Returns:
            Число удалённых строк.
        """
        ids_stmt = (
            select(TopicNotification.id)
            .where(
                or_(
                    TopicNotification.is_active.is_(False),
                    TopicNotification.read_at.is_not(None),
                ),
            )
            .limit(limit)
        )
        stmt = delete(TopicNotification).where(
            TopicNotification.id.in_(ids_stmt),
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(result.rowcount or 0)
