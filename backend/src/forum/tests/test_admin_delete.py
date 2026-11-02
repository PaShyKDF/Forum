"""Тесты удаления в админке и обезличивания пользователей."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from starlette.exceptions import HTTPException

from forum.domain.commands.auth import EnsureUserCommand
from forum.domain.exceptions import (
    AccountDeletedError,
    RegistrationDeniedError,
)
from forum.domain.models import User
from forum.interfaces.admin.views.base import BaseModelView
from forum.interfaces.admin.views.users import UserAdmin
from forum.service_layer.handlers.visitors import (
    merge_guest_on_login,
)
from forum.service_layer.user_deletion import (
    DELETED_USER_DISPLAY_NAME,
    anonymize_user,
    public_display_name,
)


def _make_user(**overrides) -> User:
    user = User(
        uid=overrides.get('uid', uuid.uuid4()),
        username=overrides.get('username', 'alice'),
        email=overrides.get('email', 'alice@example.com'),
        email_verified=True,
        display_name=overrides.get('display_name', 'Alice'),
        initials=overrides.get('initials', 'A'),
        avatar_url='https://cdn/a.png',
        avatar_mime='image/png',
        last_ip=overrides.get('last_ip', '1.2.3.4'),
        last_country='RU',
        last_city='Moscow',
        anon_id=overrides.get('anon_id', None),
        is_guest=False,
        is_active=True,
        is_deleted=False,
    )
    return user


def test_anonymize_user_keeps_email_and_ip():
    user = _make_user()
    email = user.email
    last_ip = user.last_ip

    anonymize_user(user)

    assert user.is_deleted is True
    assert user.is_active is False
    assert user.display_name == DELETED_USER_DISPLAY_NAME
    assert user.email == email
    assert user.last_ip == last_ip
    assert user.avatar_url is None
    assert user.avatar_mime is None
    assert user.anon_id is None
    assert user.username.startswith('deleted-')


def test_public_display_name_for_deleted():
    user = _make_user()
    anonymize_user(user)
    assert public_display_name(user) == DELETED_USER_DISPLAY_NAME


def test_user_topics_posts_without_delete_orphan():
    topics_rel = User.__mapper__.relationships['topics']
    posts_rel = User.__mapper__.relationships['posts']
    assert 'delete-orphan' not in (topics_rel.cascade or set())
    assert 'delete-orphan' not in (posts_rel.cascade or set())


@pytest.mark.asyncio
async def test_base_delete_model_requires_confirm():
    view = object.__new__(BaseModelView)
    request = MagicMock()
    request.query_params = {}

    with pytest.raises(HTTPException) as exc:
        await BaseModelView.delete_model(
            view,
            request,
            pk=1,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_user_admin_delete_anonymizes():
    user = _make_user()
    session = AsyncMock()
    session.get = AsyncMock(return_value=user)
    session.commit = AsyncMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    view = object.__new__(UserAdmin)
    view.session_maker = MagicMock(return_value=session_cm)

    request = MagicMock()
    request.query_params = {'confirm': '1'}
    request.cookies = {}

    await UserAdmin.delete_model(view, request, str(user.uid))

    assert user.is_deleted is True
    assert user.email == 'alice@example.com'
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_user_admin_cannot_delete_self():
    uid = uuid.uuid4()
    view = object.__new__(UserAdmin)
    request = MagicMock()
    request.query_params = {'confirm': '1'}
    request.cookies = {'access_token': 'tok'}

    with patch(
        'forum.interfaces.admin.views.users'
        '.admin_uid_from_request_token',
        return_value=uid,
    ):
        with pytest.raises(HTTPException) as exc:
            await UserAdmin.delete_model(
                view,
                request,
                str(uid),
            )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_merge_blocks_deleted_account():
    uid = uuid.uuid4()
    existing = SimpleNamespace(
        uid=uid,
        is_deleted=True,
        last_ip=None,
        last_country=None,
    )
    uow = AsyncMock()
    uow.user_repository.get_by_id = AsyncMock(
        return_value=existing,
    )
    uow.user_repository.get_by_anon_id = AsyncMock(
        return_value=None,
    )

    with pytest.raises(AccountDeletedError):
        await merge_guest_on_login(
            EnsureUserCommand(
                uid=uid,
                username='alice',
                email='alice@example.com',
                email_verified=True,
                display_name='Alice',
            ),
            uow,
            anon_id=None,
        )


@pytest.mark.asyncio
async def test_merge_blocks_banned_email():
    uid = uuid.uuid4()
    uow = AsyncMock()
    uow.user_repository.get_by_id = AsyncMock(
        return_value=None,
    )
    uow.user_repository.get_by_anon_id = AsyncMock(
        return_value=None,
    )
    uow.user_repository.get_deleted_by_email = AsyncMock(
        return_value=SimpleNamespace(uid=uuid.uuid4()),
    )
    uow.user_repository.get_deleted_by_last_ip = AsyncMock(
        return_value=None,
    )

    with pytest.raises(RegistrationDeniedError) as exc:
        await merge_guest_on_login(
            EnsureUserCommand(
                uid=uid,
                username='bob',
                email='alice@example.com',
                email_verified=True,
                display_name='Bob',
                client_ip='9.9.9.9',
            ),
            uow,
            anon_id=None,
        )
    assert 'email' in str(exc.value).lower()
    uow.user_repository.create.assert_not_called()


@pytest.mark.asyncio
async def test_merge_blocks_banned_ip():
    uid = uuid.uuid4()
    uow = AsyncMock()
    uow.user_repository.get_by_id = AsyncMock(
        return_value=None,
    )
    uow.user_repository.get_by_anon_id = AsyncMock(
        return_value=None,
    )
    uow.user_repository.get_deleted_by_email = AsyncMock(
        return_value=None,
    )
    uow.user_repository.get_deleted_by_last_ip = AsyncMock(
        return_value=SimpleNamespace(uid=uuid.uuid4()),
    )

    with pytest.raises(RegistrationDeniedError) as exc:
        await merge_guest_on_login(
            EnsureUserCommand(
                uid=uid,
                username='bob',
                email='bob@example.com',
                email_verified=True,
                display_name='Bob',
                client_ip='1.2.3.4',
            ),
            uow,
            anon_id=None,
        )
    assert 'ip' in str(exc.value).lower()
    uow.user_repository.create.assert_not_called()
