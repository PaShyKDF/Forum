"""Тесты ACL: видимость категорий/тем и admin-only."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from forum.domain import commands
from forum.domain.exceptions import (
    DomainError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from forum.service_layer.access_control import (
    can_read_category,
    can_read_topic,
    filter_visible_topics,
    require_admin,
    require_category_read,
    require_topic_read,
)
from forum.service_layer.handlers.acl import (
    handle_set_category_members_command,
    handle_set_category_visibility_command,
    handle_set_topic_members_command,
    handle_set_topic_visibility_command,
)
from forum.service_layer.handlers.categories import (
    handle_create_category_command,
)
from forum.service_layer.handlers.topics import (
    handle_create_topic_command,
)


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _category(
    *,
    category_id: int = 1,
    is_restricted: bool = False,
    is_active: bool = True,
):
    return SimpleNamespace(
        id=category_id,
        is_restricted=is_restricted,
        is_active=is_active,
    )


def _topic(
    *,
    topic_id: int = 10,
    category_id: int = 1,
    is_restricted: bool = False,
    is_active: bool = True,
    category=None,
):
    return SimpleNamespace(
        id=topic_id,
        category_id=category_id,
        is_restricted=is_restricted,
        is_active=is_active,
        category=category,
        is_closed=False,
    )


def _make_uow(
    *,
    category_access: set[tuple[int, uuid.UUID]] | None = None,
    topic_access: set[tuple[int, uuid.UUID]] | None = None,
    any_topic_in_category: (
        set[tuple[int, uuid.UUID]] | None
    ) = None,
):
    category_access = category_access or set()
    topic_access = topic_access or set()
    any_topic_in_category = any_topic_in_category or set()

    acl = AsyncMock()

    async def has_cat(cid, uid):
        return (cid, uid) in category_access

    async def has_topic(tid, uid):
        return (tid, uid) in topic_access

    async def has_any(cid, uid):
        return (cid, uid) in any_topic_in_category

    acl.user_has_category_access.side_effect = has_cat
    acl.user_has_topic_access.side_effect = has_topic
    acl.user_has_any_topic_access_in_category.side_effect = (
        has_any
    )
    acl.list_category_users = AsyncMock(return_value=[])
    acl.list_topic_users = AsyncMock(return_value=[])
    acl.set_category_users = AsyncMock()
    acl.set_topic_users = AsyncMock()

    uow = AsyncMock()
    uow.content_acl_repository = acl
    uow.category_repository = AsyncMock()
    uow.section_repository = AsyncMock()
    uow.topic_repository = AsyncMock()
    uow.post_repository = AsyncMock()
    uow.commit = AsyncMock()
    return uow


def test_require_admin_rejects_non_admin():
    with pytest.raises(PermissionDeniedError):
        require_admin(False)


@pytest.mark.asyncio
async def test_open_category_visible_to_guest():
    uow = _make_uow()
    category = _category(is_restricted=False)
    assert await can_read_category(
        uow,
        category,
        user_uid=None,
    )


@pytest.mark.asyncio
async def test_restricted_category_hidden_without_acl():
    uow = _make_uow()
    category = _category(is_restricted=True)
    user = _uid()
    assert not await can_read_category(
        uow,
        category,
        user_uid=user,
    )


@pytest.mark.asyncio
async def test_restricted_category_visible_with_category_acl():
    user = _uid()
    uow = _make_uow(category_access={(1, user)})
    category = _category(is_restricted=True)
    assert await can_read_category(
        uow,
        category,
        user_uid=user,
    )


@pytest.mark.asyncio
async def test_restricted_category_visible_via_topic_acl():
    user = _uid()
    uow = _make_uow(any_topic_in_category={(1, user)})
    category = _category(is_restricted=True)
    assert await can_read_category(
        uow,
        category,
        user_uid=user,
    )


@pytest.mark.asyncio
async def test_admin_sees_restricted_category():
    uow = _make_uow()
    category = _category(is_restricted=True)
    assert await can_read_category(
        uow,
        category,
        user_uid=None,
        is_admin=True,
    )


@pytest.mark.asyncio
async def test_category_acl_sees_all_topics_in_restricted():
    user = _uid()
    parent = _category(is_restricted=True)
    topic = _topic(is_restricted=False, category=parent)
    uow = _make_uow(category_access={(1, user)})
    assert await can_read_topic(
        uow,
        topic,
        category=parent,
        user_uid=user,
    )


@pytest.mark.asyncio
async def test_topic_acl_in_restricted_category_only_that_topic():
    user = _uid()
    parent = _category(is_restricted=True)
    allowed = _topic(
        topic_id=10,
        is_restricted=False,
        category=parent,
    )
    other = _topic(
        topic_id=11,
        is_restricted=False,
        category=parent,
    )
    uow = _make_uow(
        topic_access={(10, user)},
        any_topic_in_category={(1, user)},
    )
    assert await can_read_topic(
        uow,
        allowed,
        category=parent,
        user_uid=user,
    )
    assert not await can_read_topic(
        uow,
        other,
        category=parent,
        user_uid=user,
    )


@pytest.mark.asyncio
async def test_category_plus_topic_acl_limits_to_topic_list():
    """Category ACL + topic ACL → только темы из topic ACL."""
    user = _uid()
    parent = _category(is_restricted=True)
    allowed = _topic(
        topic_id=10,
        category=parent,
    )
    other = _topic(
        topic_id=11,
        category=parent,
    )
    uow = _make_uow(
        category_access={(1, user)},
        topic_access={(10, user)},
        any_topic_in_category={(1, user)},
    )
    assert await can_read_topic(
        uow,
        allowed,
        category=parent,
        user_uid=user,
    )
    assert not await can_read_topic(
        uow,
        other,
        category=parent,
        user_uid=user,
    )


@pytest.mark.asyncio
async def test_restricted_topic_in_open_category():
    user = _uid()
    parent = _category(is_restricted=False)
    topic = _topic(is_restricted=True, category=parent)
    uow_no = _make_uow()
    uow_yes = _make_uow(topic_access={(10, user)})
    assert not await can_read_topic(
        uow_no,
        topic,
        category=parent,
        user_uid=user,
    )
    assert await can_read_topic(
        uow_yes,
        topic,
        category=parent,
        user_uid=user,
    )


@pytest.mark.asyncio
async def test_filter_visible_topics_hides_restricted():
    user = _uid()
    parent = _category(is_restricted=False)
    open_topic = _topic(
        topic_id=1,
        is_restricted=False,
        category=parent,
    )
    hidden = _topic(
        topic_id=2,
        is_restricted=True,
        category=parent,
    )
    uow = _make_uow(topic_access={(2, user)})
    visible = await filter_visible_topics(
        uow,
        [open_topic, hidden],
        user_uid=_uid(),
        category=parent,
    )
    assert [item.id for item in visible] == [1]
    visible_allowed = await filter_visible_topics(
        uow,
        [open_topic, hidden],
        user_uid=user,
        category=parent,
    )
    assert [item.id for item in visible_allowed] == [1, 2]


@pytest.mark.asyncio
async def test_require_category_read_hides_as_404():
    uow = _make_uow()
    category = _category(is_restricted=True)
    uow.category_repository.get_active_by_id = AsyncMock(
        return_value=category,
    )
    with pytest.raises(EntityNotFoundError):
        await require_category_read(
            uow,
            1,
            user_uid=_uid(),
        )


@pytest.mark.asyncio
async def test_require_topic_read_hides_as_404():
    parent = _category(is_restricted=False)
    topic = _topic(is_restricted=True, category=parent)
    uow = _make_uow()
    uow.topic_repository.get_active_by_id = AsyncMock(
        return_value=topic,
    )
    with pytest.raises(EntityNotFoundError):
        await require_topic_read(
            uow,
            10,
            user_uid=_uid(),
        )


@pytest.mark.asyncio
async def test_visibility_toggle_keeps_acl_list():
    category = _category(is_restricted=True)
    uow = _make_uow()
    uow.category_repository.get_by_id = AsyncMock(
        return_value=category,
    )
    stored = [_uid(), _uid()]
    uow.content_acl_repository.list_category_user_ids = (
        AsyncMock(return_value=stored)
    )

    result = await handle_set_category_visibility_command(
        commands.SetCategoryVisibilityCommand(
            category_id=1,
            is_restricted=False,
            actor_uid=_uid(),
            is_admin=True,
        ),
        uow,
    )
    assert result['is_restricted'] is False
    assert category.is_restricted is False
    uow.content_acl_repository.set_category_users.assert_not_called()

    await handle_set_category_visibility_command(
        commands.SetCategoryVisibilityCommand(
            category_id=1,
            is_restricted=True,
            actor_uid=_uid(),
            is_admin=True,
        ),
        uow,
    )
    assert category.is_restricted is True
    uow.content_acl_repository.set_category_users.assert_not_called()


@pytest.mark.asyncio
async def test_set_members_admin_only():
    with pytest.raises(PermissionDeniedError):
        await handle_set_category_members_command(
            commands.SetCategoryMembersCommand(
                category_id=1,
                user_uids=[_uid()],
                actor_uid=_uid(),
                is_admin=False,
            ),
            _make_uow(),
        )
    with pytest.raises(PermissionDeniedError):
        await handle_set_topic_members_command(
            commands.SetTopicMembersCommand(
                topic_id=1,
                user_uids=[_uid()],
                actor_uid=_uid(),
                is_admin=False,
            ),
            _make_uow(),
        )
    with pytest.raises(PermissionDeniedError):
        await handle_set_topic_visibility_command(
            commands.SetTopicVisibilityCommand(
                topic_id=1,
                is_restricted=True,
                actor_uid=_uid(),
                is_admin=False,
            ),
            _make_uow(),
        )


@pytest.mark.asyncio
async def test_create_restricted_topic_admin_only():
    uow = _make_uow()
    parent = _category(is_restricted=False)
    uow.category_repository.get_active_by_id = AsyncMock(
        return_value=parent,
    )
    with pytest.raises(DomainError) as exc_info:
        await handle_create_topic_command(
            commands.CreateTopicCommand(
                category_id=1,
                author_id=_uid(),
                title='Private',
                body='Hello',
                is_restricted=True,
                allowed_user_uids=[_uid()],
                is_admin=False,
            ),
            uow,
        )
    assert exc_info.value.error_code == 'PERMISSION_DENIED'


@pytest.mark.asyncio
async def test_create_category_admin_only():
    uow = _make_uow()
    uow.section_repository.get_active_by_id = AsyncMock(
        return_value=SimpleNamespace(id=5, title='Sec'),
    )
    with pytest.raises(PermissionDeniedError):
        await handle_create_category_command(
            commands.CreateCategoryCommand(
                section_id=5,
                title='New cat',
                is_admin=False,
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_create_open_category_as_admin():
    uow = _make_uow()
    section = SimpleNamespace(id=5, title='Sec')
    uow.section_repository.get_active_by_id = AsyncMock(
        return_value=section,
    )
    uow.category_repository.get_by_title = AsyncMock(
        return_value=None,
    )
    uow.category_repository.get_max_position = AsyncMock(
        return_value=2,
    )

    async def add_category(entity):
        entity.id = 42
        return entity

    uow.category_repository.add = AsyncMock(
        side_effect=add_category,
    )
    result = await handle_create_category_command(
        commands.CreateCategoryCommand(
            section_id=5,
            title='Open cat',
            description='Hello',
            is_restricted=False,
            is_admin=True,
        ),
        uow,
    )
    assert result.id == 42
    assert result.title == 'Open cat'
    assert result.section_id == 5
    uow.content_acl_repository.set_category_users.assert_not_called()
    uow.commit.assert_awaited_once()
    added = uow.category_repository.add.await_args.args[0]
    assert added.position == 3
    assert added.is_restricted is False


@pytest.mark.asyncio
async def test_create_restricted_category_with_members():
    uow = _make_uow()
    section = SimpleNamespace(id=5, title='Sec')
    member_uid = _uid()
    uow.section_repository.get_active_by_id = AsyncMock(
        return_value=section,
    )
    uow.category_repository.get_by_title = AsyncMock(
        return_value=None,
    )
    uow.category_repository.get_max_position = AsyncMock(
        return_value=-1,
    )

    async def add_category(entity):
        entity.id = 77
        return entity

    uow.category_repository.add = AsyncMock(
        side_effect=add_category,
    )
    result = await handle_create_category_command(
        commands.CreateCategoryCommand(
            section_id=5,
            title='Hidden',
            is_restricted=True,
            allowed_user_uids=[member_uid],
            is_admin=True,
        ),
        uow,
    )
    assert result.id == 77
    uow.content_acl_repository.set_category_users.assert_awaited_once_with(
        77,
        [member_uid],
    )


@pytest.mark.asyncio
async def test_set_category_members_updates_acl():
    category = _category(is_restricted=True)
    uow = _make_uow()
    uow.category_repository.get_by_id = AsyncMock(
        return_value=category,
    )
    members = [
        SimpleNamespace(
            uid=_uid(),
            username='alice',
            display_name='Alice',
            initials='A',
            avatar_mime=None,
            avatar_url=None,
        ),
    ]
    uow.content_acl_repository.list_category_users = (
        AsyncMock(return_value=members)
    )
    uids = [members[0].uid]
    result = await handle_set_category_members_command(
        commands.SetCategoryMembersCommand(
            category_id=1,
            user_uids=uids,
            actor_uid=_uid(),
            is_admin=True,
        ),
        uow,
    )
    uow.content_acl_repository.set_category_users.assert_awaited_once_with(
        1,
        uids,
    )
    assert len(result) == 1
    assert result[0].username == 'alice'
