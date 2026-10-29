"""Тесты учёта и очистки просмотров тем."""

from contextlib import asynccontextmanager
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from forum.adapters.repositories.topic_views import (
    TopicViewRepository,
)
from forum.domain.commands.topics import (
    RecordTopicViewCommand,
)
from forum.service_layer.handlers.topics import (
    _viewer_key,
    handle_record_topic_view_command,
)
from forum.service_layer.tasks.topic_views import (
    cleanup_old_topic_views_core,
)


def test_viewer_key_for_user():
    uid = uuid.uuid4()
    assert _viewer_key(uid, None) == f'u:{uid}'


def test_viewer_key_for_guest():
    assert _viewer_key(None, 'abc') == 'a:abc'


def test_viewer_key_without_identity():
    assert _viewer_key(None, None) is None


@pytest.mark.asyncio
async def test_record_daily_view_increments_on_insert():
    """
    Первый INSERT возвращает id — views_count +1.
    """
    session = AsyncMock()
    insert_result = SimpleNamespace(
        scalar_one_or_none=lambda: 42,
    )
    update_result = SimpleNamespace(rowcount=1)
    session.execute = AsyncMock(
        side_effect=[insert_result, update_result],
    )
    session.flush = AsyncMock()
    repo = TopicViewRepository(session)

    recorded = await repo.record_daily_view(
        topic_id=7,
        viewer_key='u:111',
        view_date=date(2026, 10, 29),
        viewed_at=datetime(2026, 10, 29, 12, 0, 0),
        user_id=uuid.uuid4(),
    )

    assert recorded is True
    assert session.execute.await_count == 2
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_record_daily_view_skips_on_conflict():
    """
    CONFLICT без returning id — без UPDATE счётчика.
    """
    session = AsyncMock()
    insert_result = SimpleNamespace(
        scalar_one_or_none=lambda: None,
    )
    session.execute = AsyncMock(
        return_value=insert_result,
    )
    session.flush = AsyncMock()
    repo = TopicViewRepository(session)

    recorded = await repo.record_daily_view(
        topic_id=7,
        viewer_key='a:guest',
        view_date=date(2026, 10, 29),
        viewed_at=datetime(2026, 10, 29, 12, 0, 0),
        anon_id='guest',
    )

    assert recorded is False
    assert session.execute.await_count == 1
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_record_topic_view_user_key():
    uid = uuid.uuid4()
    uow = AsyncMock()
    uow.topic_view_repository = AsyncMock()
    uow.topic_view_repository.record_daily_view = (
        AsyncMock(return_value=True)
    )
    uow.commit = AsyncMock()

    with patch(
        'forum.service_layer.handlers.topics.moscow_today',
        return_value=date(2026, 10, 29),
    ), patch(
        'forum.service_layer.handlers.topics.utc_now_naive',
        return_value=datetime(2026, 10, 29, 9, 0, 0),
    ):
        recorded = await handle_record_topic_view_command(
            RecordTopicViewCommand(
                topic_id=5,
                user_uid=uid,
            ),
            uow,
        )

    assert recorded is True
    kwargs = (
        uow.topic_view_repository.record_daily_view
        .await_args.kwargs
    )
    assert kwargs['viewer_key'] == f'u:{uid}'
    assert kwargs['user_id'] == uid
    assert kwargs['anon_id'] is None
    uow.commit.assert_awaited()


@pytest.mark.asyncio
async def test_handle_record_topic_view_guest_key():
    uow = AsyncMock()
    uow.topic_view_repository = AsyncMock()
    uow.topic_view_repository.record_daily_view = (
        AsyncMock(return_value=False)
    )
    uow.commit = AsyncMock()

    with patch(
        'forum.service_layer.handlers.topics.moscow_today',
        return_value=date(2026, 10, 29),
    ), patch(
        'forum.service_layer.handlers.topics.utc_now_naive',
        return_value=datetime(2026, 10, 29, 9, 0, 0),
    ):
        recorded = await handle_record_topic_view_command(
            RecordTopicViewCommand(
                topic_id=5,
                anon_id='anon-1',
            ),
            uow,
        )

    assert recorded is False
    kwargs = (
        uow.topic_view_repository.record_daily_view
        .await_args.kwargs
    )
    assert kwargs['viewer_key'] == 'a:anon-1'
    assert kwargs['anon_id'] == 'anon-1'


@pytest.mark.asyncio
async def test_handle_record_topic_view_without_identity():
    uow = AsyncMock()
    uow.topic_view_repository = AsyncMock()
    uow.commit = AsyncMock()

    recorded = await handle_record_topic_view_command(
        RecordTopicViewCommand(topic_id=5),
        uow,
    )

    assert recorded is False
    repo = uow.topic_view_repository
    repo.record_daily_view.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_older_than_batch_returns_rowcount():
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=SimpleNamespace(rowcount=3),
    )
    session.flush = AsyncMock()
    repo = TopicViewRepository(session)

    deleted = await repo.delete_older_than_batch(
        before_date=date(2026, 10, 1),
        limit=10,
    )

    assert deleted == 3
    session.execute.assert_awaited()
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_cleanup_old_topic_views_core_batches():
    calls = {'n': 0}

    @asynccontextmanager
    async def factory():
        uow = AsyncMock()
        calls['n'] += 1
        if calls['n'] == 1:
            deleted = 4
        elif calls['n'] == 2:
            deleted = 1
        else:
            deleted = 0
        uow.topic_view_repository.delete_older_than_batch = (
            AsyncMock(return_value=deleted)
        )
        uow.commit = AsyncMock()
        yield uow

    with patch(
        'forum.service_layer.tasks.topic_views.moscow_today',
        return_value=date(2026, 10, 29),
    ):
        result = await cleanup_old_topic_views_core(
            factory,
            retention_days=30,
            batch_size=4,
            max_batches=10,
        )

    assert result.deleted_count == 5
    assert result.batches_count == 2
    assert result.errors_count == 0


@pytest.mark.asyncio
async def test_cleanup_retention_one_deletes_yesterday():
    """
    retention=1 при 29.10 удаляет view_date < 29.10.
    """
    captured = {}

    @asynccontextmanager
    async def factory():
        uow = AsyncMock()

        async def delete_batch(*, before_date, limit):
            captured['before_date'] = before_date
            return 0

        uow.topic_view_repository.delete_older_than_batch = (
            delete_batch
        )
        uow.commit = AsyncMock()
        yield uow

    with patch(
        'forum.service_layer.tasks.topic_views.moscow_today',
        return_value=date(2026, 10, 29),
    ):
        await cleanup_old_topic_views_core(
            factory,
            retention_days=1,
            batch_size=10,
            max_batches=1,
        )

    assert captured['before_date'] == date(2026, 10, 29)
