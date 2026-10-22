"""Тесты редактирования названия темы."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from forum.domain import commands
from forum.domain.exceptions import (
    EditWindowExpiredError,
    PermissionDeniedError,
    TopicTitleExistsError,
)
from forum.service_layer.assemblers import can_edit_topic_title
from forum.service_layer.handlers.topics import (
    handle_update_topic_title_command,
)


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _topic(
    *,
    topic_id: int = 10,
    category_id: int = 1,
    author_id: uuid.UUID | None = None,
    title: str = 'Old title',
    created_at: datetime | None = None,
    is_restricted: bool = False,
):
    return SimpleNamespace(
        id=topic_id,
        category_id=category_id,
        author_id=author_id or _uid(),
        title=title,
        created_at=created_at or datetime.now(),
        is_restricted=is_restricted,
        is_active=True,
        is_closed=False,
        category=SimpleNamespace(
            id=category_id,
            is_restricted=False,
            is_active=True,
        ),
    )


def _make_uow(topic):
    uow = AsyncMock()
    uow.topic_repository = AsyncMock()
    uow.category_repository = AsyncMock()
    uow.content_acl_repository = AsyncMock()
    uow.topic_repository.get_active_by_id = AsyncMock(
        return_value=topic,
    )
    uow.topic_repository.get_by_category_and_title = (
        AsyncMock(return_value=None)
    )

    async def update(entity):
        return entity

    uow.topic_repository.update = AsyncMock(side_effect=update)
    uow.commit = AsyncMock()
    return uow


def test_can_edit_topic_title_within_window():
    author = _uid()
    topic = _topic(
        author_id=author,
        created_at=datetime.now() - timedelta(hours=1),
    )
    assert can_edit_topic_title(topic, author) is True


def test_can_edit_topic_title_after_window():
    author = _uid()
    topic = _topic(
        author_id=author,
        created_at=datetime.now() - timedelta(hours=25),
    )
    assert can_edit_topic_title(topic, author) is False


def test_can_edit_topic_title_rejects_non_author():
    topic = _topic(author_id=_uid())
    assert can_edit_topic_title(topic, _uid()) is False


@pytest.mark.asyncio
async def test_update_topic_title_success():
    author = _uid()
    topic = _topic(author_id=author)
    uow = _make_uow(topic)

    result = await handle_update_topic_title_command(
        commands.UpdateTopicTitleCommand(
            topic_id=topic.id,
            author_id=author,
            title='  New title  ',
        ),
        uow,
    )

    assert result.id == topic.id
    assert result.title == 'New title'
    assert result.can_edit_title is True
    assert topic.title == 'New title'
    uow.topic_repository.update.assert_awaited_once()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_topic_title_permission_denied():
    topic = _topic(author_id=_uid())
    uow = _make_uow(topic)

    with pytest.raises(PermissionDeniedError):
        await handle_update_topic_title_command(
            commands.UpdateTopicTitleCommand(
                topic_id=topic.id,
                author_id=_uid(),
                title='Hacked',
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_update_topic_title_window_expired():
    author = _uid()
    topic = _topic(
        author_id=author,
        created_at=datetime.now() - timedelta(hours=30),
    )
    uow = _make_uow(topic)

    with pytest.raises(EditWindowExpiredError) as exc_info:
        await handle_update_topic_title_command(
            commands.UpdateTopicTitleCommand(
                topic_id=topic.id,
                author_id=author,
                title='Too late',
            ),
            uow,
        )
    assert exc_info.value.error_code == 'EDIT_WINDOW_EXPIRED'


@pytest.mark.asyncio
async def test_update_topic_title_duplicate():
    author = _uid()
    topic = _topic(author_id=author, title='Mine')
    uow = _make_uow(topic)
    uow.topic_repository.get_by_category_and_title = (
        AsyncMock(
            return_value=SimpleNamespace(
                id=99,
                title='Taken',
            ),
        )
    )

    with pytest.raises(TopicTitleExistsError):
        await handle_update_topic_title_command(
            commands.UpdateTopicTitleCommand(
                topic_id=topic.id,
                author_id=author,
                title='Taken',
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_update_topic_title_same_title_allowed():
    author = _uid()
    topic = _topic(author_id=author, title='Same')
    uow = _make_uow(topic)
    uow.topic_repository.get_by_category_and_title = (
        AsyncMock(return_value=topic)
    )

    result = await handle_update_topic_title_command(
        commands.UpdateTopicTitleCommand(
            topic_id=topic.id,
            author_id=author,
            title='Same',
        ),
        uow,
    )
    assert result.title == 'Same'


@pytest.mark.asyncio
async def test_update_topic_title_respects_env_window():
    author = _uid()
    topic = _topic(
        author_id=author,
        created_at=datetime.now() - timedelta(hours=2),
    )
    uow = _make_uow(topic)

    with patch(
        'forum.service_layer.handlers.topics.configuration',
    ) as cfg:
        cfg.discussions.topic_edit_window_hours = 1
        with pytest.raises(EditWindowExpiredError):
            await handle_update_topic_title_command(
                commands.UpdateTopicTitleCommand(
                    topic_id=topic.id,
                    author_id=author,
                    title='Late',
                ),
                uow,
            )
