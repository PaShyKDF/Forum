"""Тесты режима темы только для чтения (is_closed)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from forum.domain import commands
from forum.domain.exceptions import (
    DomainError,
    PermissionDeniedError,
    TopicClosedError,
)
from forum.service_layer.access_control import (
    require_topic_write,
)
from forum.service_layer.handlers.acl import (
    handle_set_topic_closed_command,
)
from forum.service_layer.handlers.topics import (
    handle_create_topic_command,
)


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _category(*, category_id: int = 1):
    return SimpleNamespace(
        id=category_id,
        is_restricted=False,
        is_active=True,
    )


def _make_uow(*, category=None, topic=None):
    uow = AsyncMock()
    uow.content_acl_repository = AsyncMock()
    uow.category_repository = AsyncMock()
    uow.topic_repository = AsyncMock()
    uow.post_repository = AsyncMock()
    uow.commit = AsyncMock()
    if category is not None:
        uow.category_repository.get_active_by_id = (
            AsyncMock(return_value=category)
        )
    if topic is not None:
        uow.topic_repository.get_by_id = AsyncMock(
            return_value=topic,
        )
        uow.topic_repository.get_active_by_id = AsyncMock(
            return_value=topic,
        )
    return uow


@pytest.mark.asyncio
async def test_create_closed_topic_rejects_non_admin():
    uow = _make_uow(category=_category())
    with pytest.raises(DomainError) as exc_info:
        await handle_create_topic_command(
            commands.CreateTopicCommand(
                category_id=1,
                author_id=_uid(),
                title='Read only',
                body='Hello',
                is_closed=True,
                is_admin=False,
            ),
            uow,
        )
    assert exc_info.value.error_code == 'PERMISSION_DENIED'


@pytest.mark.asyncio
async def test_create_closed_topic_as_admin():
    uow = _make_uow(category=_category())
    uow.topic_repository.get_by_category_and_title = (
        AsyncMock(return_value=None)
    )
    uow.topic_repository.get_max_position = AsyncMock(
        return_value=5,
    )

    async def add_topic(entity):
        entity.id = 77
        return entity

    async def add_post(entity):
        entity.id = 1
        return entity

    uow.topic_repository.add = AsyncMock(
        side_effect=add_topic,
    )
    uow.post_repository.add = AsyncMock(
        side_effect=add_post,
    )
    limits_path = (
        'forum.service_layer.handlers.topics'
        '.check_topic_limits'
    )
    with patch(limits_path, new_callable=AsyncMock):
        result = await handle_create_topic_command(
            commands.CreateTopicCommand(
                category_id=1,
                author_id=_uid(),
                title='Read only',
                body='Hello',
                is_closed=True,
                is_admin=True,
            ),
            uow,
        )
    assert result.id == 77
    added = uow.topic_repository.add.await_args.args[0]
    assert added.is_closed is True
    assert added.position == 6
    uow.topic_repository.get_max_position.assert_awaited_once_with(
        1,
    )
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_topic_closed_as_admin():
    topic = SimpleNamespace(
        id=10,
        is_closed=False,
    )
    uow = _make_uow(topic=topic)
    result = await handle_set_topic_closed_command(
        commands.SetTopicClosedCommand(
            topic_id=10,
            is_closed=True,
            actor_uid=_uid(),
            is_admin=True,
        ),
        uow,
    )
    assert result == {'id': 10, 'is_closed': True}
    assert topic.is_closed is True
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_topic_closed_rejects_non_admin():
    with pytest.raises(PermissionDeniedError):
        await handle_set_topic_closed_command(
            commands.SetTopicClosedCommand(
                topic_id=10,
                is_closed=True,
                actor_uid=_uid(),
                is_admin=False,
            ),
            _make_uow(),
        )


@pytest.mark.asyncio
async def test_require_topic_write_closed_rejects_user():
    topic = SimpleNamespace(
        id=10,
        category_id=1,
        is_restricted=False,
        is_active=True,
        is_closed=True,
        category=_category(),
    )
    uow = _make_uow(topic=topic)
    with pytest.raises(TopicClosedError):
        await require_topic_write(
            uow,
            10,
            user_uid=_uid(),
            is_admin=False,
        )


@pytest.mark.asyncio
async def test_require_topic_write_closed_allows_admin():
    topic = SimpleNamespace(
        id=10,
        category_id=1,
        is_restricted=False,
        is_active=True,
        is_closed=True,
        category=_category(),
    )
    uow = _make_uow(topic=topic)
    result = await require_topic_write(
        uow,
        10,
        user_uid=_uid(),
        is_admin=True,
    )
    assert result is topic
