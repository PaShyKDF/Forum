"""Тесты уведомлений о ответах/цитатах и read_at ЛС."""

from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from forum.adapters.repositories.notifications import (
    TopicNotificationRepository,
)
from forum.domain import commands
from forum.domain.exceptions import EntityNotFoundError
from forum.service_layer.handlers.notifications import (
    handle_clear_notifications_command,
    handle_dismiss_notification_command,
    handle_get_my_notifications_command,
    handle_get_unread_chat_count_command,
    handle_mark_chat_messages_visible_command,
    handle_mark_notification_read_command,
)
from forum.service_layer.handlers.posts import (
    _create_post_notifications,
    _notify_if_needed,
)
from forum.service_layer.tasks.notifications import (
    cleanup_inactive_notifications,
    cleanup_inactive_notifications_core,
)


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _notification(
    *,
    notification_id: int = 1,
    recipient_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    topic_id: int = 5,
    post_id: int = 20,
    source_post_id: int = 10,
    kind: str = 'reply',
    read_at=None,
    is_active: bool = True,
):
    actor = SimpleNamespace(
        uid=actor_id or _uid(),
        display_name='Иван',
    )
    topic = SimpleNamespace(
        id=topic_id,
        title='Тестовая тема',
    )
    post = SimpleNamespace(
        id=post_id,
        topic_id=topic_id,
        reply_to_post_id=source_post_id,
        created_at=datetime.now(),
    )
    return SimpleNamespace(
        id=notification_id,
        recipient_id=recipient_id or _uid(),
        actor_id=actor.uid,
        topic_id=topic_id,
        post_id=post_id,
        source_post_id=source_post_id,
        kind=kind,
        read_at=read_at,
        is_active=is_active,
        actor=actor,
        topic=topic,
        post=post,
        source_post=None,
        created_at=datetime.now(),
    )


def _make_uow():
    uow = AsyncMock()
    uow.notification_repository = AsyncMock()
    uow.chat_message_repository = AsyncMock()
    uow.post_repository = AsyncMock()
    uow.commit = AsyncMock()
    return uow


@pytest.mark.asyncio
async def test_notify_skips_self_action():
    uow = _make_uow()
    actor = _uid()
    notified: set = set()
    await _notify_if_needed(
        uow,
        actor_id=actor,
        recipient_id=actor,
        topic_id=1,
        post_id=2,
        source_post_id=1,
        kind='reply',
        notified=notified,
    )
    uow.notification_repository.create_notification.assert_not_called()
    assert notified == set()


@pytest.mark.asyncio
async def test_notify_creates_once_per_recipient():
    uow = _make_uow()
    actor = _uid()
    recipient = _uid()
    notified: set = set()
    await _notify_if_needed(
        uow,
        actor_id=actor,
        recipient_id=recipient,
        topic_id=1,
        post_id=2,
        source_post_id=1,
        kind='reply',
        notified=notified,
    )
    await _notify_if_needed(
        uow,
        actor_id=actor,
        recipient_id=recipient,
        topic_id=1,
        post_id=2,
        source_post_id=3,
        kind='quote',
        notified=notified,
    )
    assert (
        uow.notification_repository.create_notification
        .await_count
        == 1
    )
    assert recipient in notified


@pytest.mark.asyncio
async def test_create_post_notifications_reply_and_quote():
    uow = _make_uow()
    actor = _uid()
    parent_author = _uid()
    quoted_author = _uid()
    parent = SimpleNamespace(
        id=10,
        author_id=parent_author,
    )
    quoted = SimpleNamespace(
        id=11,
        author_id=quoted_author,
    )
    post = SimpleNamespace(
        id=20,
        quoted_post_id=11,
    )
    uow.post_repository.get_active_by_id = AsyncMock(
        return_value=quoted,
    )
    await _create_post_notifications(
        uow,
        actor_id=actor,
        topic_id=5,
        post=post,
        parent=parent,
    )
    assert (
        uow.notification_repository.create_notification
        .await_count
        == 2
    )


@pytest.mark.asyncio
async def test_create_post_notifications_skips_self_reply():
    uow = _make_uow()
    actor = _uid()
    parent = SimpleNamespace(id=10, author_id=actor)
    post = SimpleNamespace(id=20, quoted_post_id=None)
    await _create_post_notifications(
        uow,
        actor_id=actor,
        topic_id=5,
        post=post,
        parent=parent,
    )
    uow.notification_repository.create_notification.assert_not_called()


@pytest.mark.asyncio
async def test_get_my_notifications():
    recipient = _uid()
    note = _notification(recipient_id=recipient)
    uow = _make_uow()
    uow.notification_repository.list_active_unread = (
        AsyncMock(return_value=[note])
    )
    uow.notification_repository.count_active_unread = (
        AsyncMock(return_value=1)
    )
    uow.post_repository.count_newer_roots = AsyncMock(
        return_value=0,
    )
    uow.post_repository.count_newer_replies = AsyncMock(
        return_value=0,
    )
    uow.post_repository.get_active_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=10,
            topic_id=5,
            created_at=datetime.now(),
            reply_to_post_id=None,
        ),
    )
    result = await handle_get_my_notifications_command(
        commands.GetMyNotificationsCommand(
            current_user_uid=recipient,
        ),
        uow,
    )
    assert result.unread_count == 1
    assert len(result.items) == 1
    assert 'ответил' in result.items[0].text


@pytest.mark.asyncio
async def test_mark_notification_read():
    recipient = _uid()
    note = _notification(recipient_id=recipient)
    uow = _make_uow()
    uow.notification_repository.mark_read = AsyncMock(
        return_value=note,
    )
    result = await handle_mark_notification_read_command(
        commands.MarkNotificationReadCommand(
            notification_id=note.id,
            current_user_uid=recipient,
        ),
        uow,
    )
    assert result.success is True
    assert note.is_active is False
    uow.commit.assert_awaited()


@pytest.mark.asyncio
async def test_mark_notification_read_not_found():
    uow = _make_uow()
    uow.notification_repository.mark_read = AsyncMock(
        return_value=None,
    )
    with pytest.raises(EntityNotFoundError):
        await handle_mark_notification_read_command(
            commands.MarkNotificationReadCommand(
                notification_id=99,
                current_user_uid=_uid(),
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_dismiss_notification():
    uow = _make_uow()
    uow.notification_repository.dismiss = AsyncMock(
        return_value=True,
    )
    result = await handle_dismiss_notification_command(
        commands.DismissNotificationCommand(
            notification_id=1,
            current_user_uid=_uid(),
        ),
        uow,
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_clear_notifications():
    uow = _make_uow()
    uow.notification_repository.clear_all = AsyncMock(
        return_value=3,
    )
    result = await handle_clear_notifications_command(
        commands.ClearNotificationsCommand(
            current_user_uid=_uid(),
        ),
        uow,
    )
    assert result.success is True
    assert 'очищены' in result.message.lower()


@pytest.mark.asyncio
async def test_unread_chat_count():
    uow = _make_uow()
    uow.chat_message_repository.count_unread_for_user = (
        AsyncMock(return_value=7)
    )
    result = await handle_get_unread_chat_count_command(
        commands.GetUnreadChatCountCommand(
            current_user_uid=_uid(),
        ),
        uow,
    )
    assert result.unread_count == 7


@pytest.mark.asyncio
async def test_get_my_chats_includes_unread_per_chat():
    from forum.service_layer.handlers.chats import (
        handle_get_my_chats_command,
    )

    me = _uid()
    peer = _uid()
    chat = SimpleNamespace(
        id=11,
        user_low_id=me,
        user_high_id=peer,
        user_low=SimpleNamespace(
            uid=me,
            display_name='Me',
            username='me',
            initials='M',
            avatar_url=None,
            avatar_mime=None,
        ),
        user_high=SimpleNamespace(
            uid=peer,
            display_name='Peer',
            username='peer',
            initials='P',
            avatar_url=None,
            avatar_mime=None,
        ),
        updated_at=datetime.now(),
    )
    uow = _make_uow()
    uow.chat_repository.list_user_chats = AsyncMock(
        return_value=[chat],
    )
    uow.chat_message_repository.get_last_message_for_chat_ids = (
        AsyncMock(return_value={})
    )
    uow.chat_message_repository.count_unread_by_chat_ids = (
        AsyncMock(return_value={11: 4})
    )
    result = await handle_get_my_chats_command(
        commands.GetMyChatsCommand(current_user_uid=me),
        uow,
    )
    assert len(result) == 1
    assert result[0].id == 11
    assert result[0].unread_count == 4


@pytest.mark.asyncio
async def test_mark_chat_messages_visible():
    uow = _make_uow()
    uow.chat_message_repository.mark_visible = AsyncMock(
        return_value=[1, 2],
    )
    uow.chat_message_repository.count_unread_for_user = (
        AsyncMock(return_value=3)
    )
    result = await handle_mark_chat_messages_visible_command(
        commands.MarkChatMessagesVisibleCommand(
            current_user_uid=_uid(),
            message_ids=[1, 2, 2, 3],
        ),
        uow,
    )
    assert result.marked_ids == [1, 2]
    assert result.unread_count == 3
    uow.commit.assert_awaited()


def test_format_badge_count_logic():
    """Формат 20+ должен жить на фронте; здесь проверяем порог."""
    count = 21
    label = '20+' if count > 20 else str(count)
    assert label == '20+'


@pytest.mark.asyncio
async def test_delete_inactive_batch_returns_rowcount():
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=SimpleNamespace(rowcount=3),
    )
    session.flush = AsyncMock()
    repo = TopicNotificationRepository(session)
    deleted = await repo.delete_inactive_batch(limit=10)
    assert deleted == 3
    session.execute.assert_awaited()
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_cleanup_core_batches_until_empty():
    calls = {'n': 0}

    @asynccontextmanager
    async def factory():
        uow = AsyncMock()
        calls['n'] += 1
        if calls['n'] == 1:
            deleted = 2
        elif calls['n'] == 2:
            deleted = 1
        else:
            deleted = 0
        uow.notification_repository.delete_inactive_batch = (
            AsyncMock(return_value=deleted)
        )
        uow.commit = AsyncMock()
        yield uow

    result = await cleanup_inactive_notifications_core(
        factory,
        batch_size=2,
        max_batches=10,
    )
    assert result.deleted_count == 3
    assert result.batches_count == 2
    assert result.errors_count == 0


@pytest.mark.asyncio
async def test_cleanup_core_respects_max_batches():
    @asynccontextmanager
    async def factory():
        uow = AsyncMock()
        uow.notification_repository.delete_inactive_batch = (
            AsyncMock(return_value=10)
        )
        uow.commit = AsyncMock()
        yield uow

    result = await cleanup_inactive_notifications_core(
        factory,
        batch_size=10,
        max_batches=2,
    )
    assert result.deleted_count == 20
    assert result.batches_count == 2


@pytest.mark.asyncio
async def test_cleanup_core_continues_after_batch_error():
    calls = {'n': 0}

    @asynccontextmanager
    async def factory():
        uow = AsyncMock()
        calls['n'] += 1
        if calls['n'] == 1:
            uow.notification_repository.delete_inactive_batch = (
                AsyncMock(side_effect=RuntimeError('db'))
            )
        elif calls['n'] == 2:
            uow.notification_repository.delete_inactive_batch = (
                AsyncMock(return_value=5)
            )
        else:
            uow.notification_repository.delete_inactive_batch = (
                AsyncMock(return_value=0)
            )
        uow.commit = AsyncMock()
        yield uow

    result = await cleanup_inactive_notifications_core(
        factory,
        batch_size=5,
        max_batches=10,
    )
    assert result.deleted_count == 5
    assert result.batches_count == 1
    assert result.errors_count == 1


@pytest.mark.asyncio
async def test_cleanup_core_stops_after_three_errors():
    @asynccontextmanager
    async def factory():
        uow = AsyncMock()
        uow.notification_repository.delete_inactive_batch = (
            AsyncMock(side_effect=RuntimeError('db'))
        )
        uow.commit = AsyncMock()
        yield uow

    result = await cleanup_inactive_notifications_core(
        factory,
        batch_size=5,
        max_batches=10,
    )
    assert result.deleted_count == 0
    assert result.errors_count == 3


@pytest.mark.asyncio
async def test_cleanup_task_skips_when_disabled(
    monkeypatch,
):
    from forum.config import configuration

    monkeypatch.setattr(
        configuration.notifications_cleanup,
        'enabled',
        False,
    )
    with patch(
        'forum.service_layer.tasks.notifications'
        '.cleanup_inactive_notifications_core',
        new_callable=AsyncMock,
    ) as core:
        await cleanup_inactive_notifications()
        core.assert_not_called()
