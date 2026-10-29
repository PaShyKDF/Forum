"""Репозиторий ежедневных просмотров тем."""

from datetime import date, datetime
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from forum.domain.models import Topic, TopicView


class TopicViewRepository:
    """Запись и очистка просмотров тем."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_daily_view(
        self,
        *,
        topic_id: int,
        viewer_key: str,
        view_date: date,
        viewed_at: datetime,
        user_id: uuid.UUID | None = None,
        anon_id: str | None = None,
    ) -> bool:
        """
        Фиксирует первый просмотр зрителя за сутки.

        INSERT ON CONFLICT DO NOTHING. Если строка
        вставилась — увеличивает Topic.views_count на 1.

        Args:
            topic_id: ID темы.
            viewer_key: u:<uid> или a:<anon_id>.
            view_date: дата по Москве.
            viewed_at: момент просмотра (UTC naive).
            user_id: uid авторизованного или None.
            anon_id: cookie гостя или None.

        Returns:
            True, если просмотр засчитан впервые за день.
        """
        stmt = (
            insert(TopicView)
            .values(
                topic_id=topic_id,
                viewer_key=viewer_key,
                user_id=user_id,
                anon_id=anon_id,
                view_date=view_date,
                viewed_at=viewed_at,
            )
            .on_conflict_do_nothing(
                constraint='uq_topic_view_topic_viewer_date',
            )
            .returning(TopicView.id)
        )
        result = await self.session.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is None:
            return False

        await self.session.execute(
            update(Topic)
            .where(Topic.id == topic_id)
            .values(
                views_count=Topic.views_count + 1,
            ),
        )
        await self.session.flush()
        return True

    async def list_topic_ids_viewed_on(
        self,
        *,
        viewer_key: str,
        view_date: date,
    ) -> list[int]:
        """
        ID тем, которые зритель открывал в указанный день.

        Args:
            viewer_key: u:<uid> или a:<anon_id>.
            view_date: дата по Москве.

        Returns:
            Список topic_id.
        """
        stmt = select(TopicView.topic_id).where(
            TopicView.viewer_key == viewer_key,
            TopicView.view_date == view_date,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_older_than_batch(
        self,
        *,
        before_date: date,
        limit: int = 500,
    ) -> int:
        """
        Удаляет пачку визитов старше before_date.

        Args:
            before_date: удалять view_date < before_date.
            limit: размер пачки.

        Returns:
            Число удалённых строк.
        """
        ids_stmt = (
            select(TopicView.id)
            .where(TopicView.view_date < before_date)
            .limit(limit)
        )
        stmt = delete(TopicView).where(
            TopicView.id.in_(ids_stmt),
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(result.rowcount or 0)
