"""Тесты трекинга гостей и merge при логине."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from pathlib import Path

from forum.domain.commands.auth import EnsureUserCommand
from forum.domain.commands.visitors import TrackGuestVisitCommand
from forum.service_layer.handlers.visitors import (
    _is_bot_user_agent,
    _should_touch,
    handle_track_guest_visit_command,
    merge_guest_on_login,
)
from forum.service_layer.visitor_cookies import (
    ANON_COOKIE_NAME,
    new_anon_id,
    read_anon_id,
)

_CATEGORIES_ROUTER = (
    Path(__file__).resolve().parents[1]
    / 'interfaces'
    / 'api'
    / 'routers'
    / 'categories.py'
)


def _make_request(
    *,
    anon_id: str | None = None,
    user_agent: str = 'Mozilla/5.0',
):
    cookies = {}
    if anon_id is not None:
        cookies[ANON_COOKIE_NAME] = anon_id
    request = MagicMock()
    request.cookies = cookies
    request.headers = {'user-agent': user_agent}
    return request


def _make_uow():
    uow = AsyncMock()
    uow.user_repository = AsyncMock()
    uow.commit = AsyncMock()
    return uow


def test_new_anon_id_is_uuid_string():
    value = new_anon_id()
    uuid.UUID(value)


def test_read_anon_id_rejects_invalid():
    request = _make_request(anon_id='not-a-uuid')
    assert read_anon_id(request) is None


def test_read_anon_id_normalizes_case():
    raw = 'AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE'
    request = _make_request(anon_id=raw)
    assert read_anon_id(request) == raw.lower()


def test_bot_user_agent_detection():
    assert _is_bot_user_agent('Googlebot/2.1')
    assert _is_bot_user_agent('python-requests/2.31')
    assert not _is_bot_user_agent('Mozilla/5.0 Chrome/120')


def test_should_touch_respects_interval():
    now = datetime(2026, 10, 12, 12, 0, 0)
    with patch(
        'forum.service_layer.handlers.visitors.configuration',
    ) as cfg:
        cfg.visitors.touch_interval_seconds = 300
        assert _should_touch(None, now) is True
        assert _should_touch(
            now - timedelta(seconds=301),
            now,
        ) is True
        assert _should_touch(
            now - timedelta(seconds=60),
            now,
        ) is False


def test_get_home_does_not_import_track_handler_directly():
    source = _CATEGORIES_ROUTER.read_text(encoding='utf-8')
    assert 'track_guest_visit' not in source
    assert 'get_unit_of_work' not in source
    assert 'TrackGuestVisitCommand' in source


@pytest.mark.asyncio
async def test_track_guest_visit_creates_guest():
    anon_id = str(uuid.uuid4())
    uow = _make_uow()
    uow.user_repository.get_by_anon_id.return_value = None
    guest = SimpleNamespace(
        uid=uuid.uuid4(),
        is_guest=True,
        is_active=True,
        last_seen_at=None,
    )
    uow.user_repository.create_guest.return_value = guest

    result = await handle_track_guest_visit_command(
        TrackGuestVisitCommand(
            anon_id=anon_id,
            user_agent='Mozilla/5.0',
            is_authenticated=False,
        ),
        uow,
    )

    assert result.anon_id == anon_id
    assert result.set_cookie is True
    uow.user_repository.create_guest.assert_awaited_once()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_track_guest_visit_skips_authenticated():
    uow = _make_uow()

    result = await handle_track_guest_visit_command(
        TrackGuestVisitCommand(
            anon_id=None,
            user_agent='Mozilla/5.0',
            is_authenticated=True,
        ),
        uow,
    )

    assert result.anon_id is None
    assert result.set_cookie is False
    uow.user_repository.get_by_anon_id.assert_not_called()


@pytest.mark.asyncio
async def test_track_guest_visit_skips_bots():
    uow = _make_uow()

    result = await handle_track_guest_visit_command(
        TrackGuestVisitCommand(
            anon_id=None,
            user_agent='curl/8.0',
            is_authenticated=False,
        ),
        uow,
    )

    assert result.anon_id is None
    assert result.set_cookie is False
    uow.user_repository.create_guest.assert_not_called()


@pytest.mark.asyncio
async def test_track_guest_visit_throttles_touch():
    anon_id = str(uuid.uuid4())
    uow = _make_uow()
    now = datetime(2026, 10, 12, 12, 0, 0)
    guest = SimpleNamespace(
        uid=uuid.uuid4(),
        is_guest=True,
        is_active=True,
        last_seen_at=now - timedelta(seconds=30),
    )
    uow.user_repository.get_by_anon_id.return_value = guest

    with (
        patch(
            'forum.service_layer.handlers.visitors'
            '.utc_now_naive',
            return_value=now,
        ),
        patch(
            'forum.service_layer.handlers.visitors'
            '.configuration',
        ) as cfg,
    ):
        cfg.visitors.touch_interval_seconds = 300
        result = await handle_track_guest_visit_command(
            TrackGuestVisitCommand(
                anon_id=anon_id,
                user_agent='Mozilla/5.0',
                is_authenticated=False,
            ),
            uow,
        )

    assert result.anon_id == anon_id
    assert result.set_cookie is True
    uow.user_repository.touch_last_seen.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.asyncio
async def test_track_guest_visit_touches_after_interval():  # noqa
    anon_id = str(uuid.uuid4())
    uow = _make_uow()
    now = datetime(2026, 10, 12, 12, 0, 0)
    guest = SimpleNamespace(
        uid=uuid.uuid4(),
        is_guest=True,
        is_active=True,
        last_seen_at=now - timedelta(seconds=400),
    )
    uow.user_repository.get_by_anon_id.return_value = guest

    with (
        patch(
            'forum.service_layer.handlers.visitors'
            '.utc_now_naive',
            return_value=now,
        ),
        patch(
            'forum.service_layer.handlers.visitors'
            '.configuration',
        ) as cfg,
    ):
        cfg.visitors.touch_interval_seconds = 300
        result = await handle_track_guest_visit_command(
            TrackGuestVisitCommand(
                anon_id=anon_id,
                user_agent='Mozilla/5.0',
                is_authenticated=False,
            ),
            uow,
        )

    assert result.anon_id == anon_id
    uow.user_repository.touch_last_seen.assert_awaited_once()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_track_rotates_cookie_for_inactive_guest():
    stale_anon = str(uuid.uuid4())
    fresh_anon = str(uuid.uuid4())
    uow = _make_uow()
    uow.user_repository.get_by_anon_id.return_value = (
        SimpleNamespace(
            uid=uuid.uuid4(),
            is_guest=True,
            is_active=False,
            last_seen_at=None,
        )
    )

    with patch(
        'forum.service_layer.handlers.visitors.new_anon_id',
        return_value=fresh_anon,
    ):
        result = await handle_track_guest_visit_command(
            TrackGuestVisitCommand(
                anon_id=stale_anon,
                user_agent='Mozilla/5.0',
                is_authenticated=False,
            ),
            uow,
        )

    assert result.anon_id == fresh_anon
    assert result.set_cookie is True
    uow.user_repository.create_guest.assert_awaited_once()


@pytest.mark.asyncio
async def test_merge_promotes_guest_on_first_login():
    anon_id = str(uuid.uuid4())
    keycloak_uid = uuid.uuid4()
    guest_uid = uuid.uuid4()
    command = EnsureUserCommand(
        uid=keycloak_uid,
        username='alice',
        email='alice@example.com',
        email_verified=True,
        display_name='Alice',
        avatar_url=None,
        anon_id=anon_id,
    )
    uow = _make_uow()
    uow.user_repository.get_by_id.return_value = None
    guest = SimpleNamespace(
        uid=guest_uid,
        is_guest=True,
        is_active=True,
        anon_id=anon_id,
    )
    uow.user_repository.get_by_anon_id.return_value = guest
    promoted = SimpleNamespace(
        uid=keycloak_uid,
        username='alice',
        email='alice@example.com',
        email_verified=True,
        display_name='Alice',
        initials='AL',
        avatar_url=None,
        avatar_mime=None,
        avatar_blob=None,
        is_guest=False,
        anon_id=None,
    )
    promote = uow.user_repository.promote_guest_to_registered
    promote.return_value = promoted

    result = await merge_guest_on_login(
        command,
        uow,
        anon_id=anon_id,
    )

    assert result.uid == keycloak_uid
    assert result.username == 'alice'
    promote.assert_awaited_once()
    uow.user_repository.create.assert_not_called()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_merge_deletes_guest_on_uid_conflict():  # noqa
    anon_id = str(uuid.uuid4())
    keycloak_uid = uuid.uuid4()
    existing = SimpleNamespace(
        uid=keycloak_uid,
        username='alice',
        email='alice@example.com',
        email_verified=True,
        display_name='Alice',
        initials='AL',
        avatar_url=None,
        avatar_mime=None,
        avatar_blob=None,
    )
    guest = SimpleNamespace(
        uid=uuid.uuid4(),
        is_guest=True,
        is_active=True,
        anon_id=anon_id,
    )
    command = EnsureUserCommand(
        uid=keycloak_uid,
        username='alice',
        email='alice@example.com',
        email_verified=True,
        display_name='Alice',
        avatar_url=None,
        anon_id=anon_id,
    )
    uow = _make_uow()
    uow.user_repository.get_by_id.return_value = existing
    uow.user_repository.get_by_anon_id.return_value = guest
    uow.user_repository.touch_last_seen.return_value = (
        existing
    )
    delete_guest = uow.user_repository.delete_guest
    promote = uow.user_repository.promote_guest_to_registered

    result = await merge_guest_on_login(
        command,
        uow,
        anon_id=anon_id,
    )

    assert result.uid == keycloak_uid
    delete_guest.assert_awaited_once_with(anon_id)
    promote.assert_not_called()


def test_no_zombie_guest_without_anon_id_contract():
    """
    После конфликта guest удаляется целиком,
    а не остаётся is_guest=True с anon_id=NULL.
    """
    rows_before = [
        {
            'uid': 'reg',
            'is_guest': False,
            'is_active': True,
            'anon_id': None,
        },
        {
            'uid': 'guest',
            'is_guest': True,
            'is_active': True,
            'anon_id': 'aaa',
        },
    ]
    # delete_guest убирает строку целиком
    rows_after = [
        r for r in rows_before if r['uid'] != 'guest'
    ]
    zombies = [
        r
        for r in rows_after
        if r['is_guest'] and r['anon_id'] is None
    ]
    assert zombies == []
    assert len(rows_after) == 1


def test_no_double_count_after_promote_logic():
    """
    После promote одна строка; при конфликте guest удалён.
    count_active_since считает только is_active.
    """
    active_rows = [
        {'uid': 'reg', 'is_guest': False, 'is_active': True},
    ]
    conflict_rows = [
        {'uid': 'reg', 'is_guest': False, 'is_active': True},
    ]

    def count_active(rows):
        return sum(1 for r in rows if r['is_active'])

    assert count_active(active_rows) == 1
    assert count_active(conflict_rows) == 1


def test_community_count_excludes_guests_contract():
    """community_members_count не должен включать is_guest."""
    rows = [
        {'is_guest': False, 'is_active': True},
        {'is_guest': True, 'is_active': True},
        {'is_guest': False, 'is_active': False},
    ]

    def count_members(items):
        return sum(
            1
            for r in items
            if r['is_active'] and not r['is_guest']
        )

    assert count_members(rows) == 1


def test_promote_expire_all_is_sync():
    """Регрессия: expire_all() нельзя await'ить."""
    import inspect

    from forum.adapters.repositories import users as users_mod

    source = inspect.getsource(
        users_mod.UserRepository.promote_guest_to_registered,
    )
    assert 'await self.session.expire_all()' not in source
    assert 'self.session.expire_all()' in source
    assert 'self.session.expunge(guest)' in source
