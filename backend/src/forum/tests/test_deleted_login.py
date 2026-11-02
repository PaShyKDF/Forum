"""Тесты отказа во входе для удалённого аккаунта."""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from forum.config import configuration
from forum.domain.exceptions import AccountDeletedError
from forum.interfaces.api.routers import auth as auth_router
from forum.service_layer.auth_cookies import LOGIN_NOTICE_COOKIE


@pytest.mark.asyncio
async def test_denied_login_redirect_uses_frontend_url():
    response = auth_router._denied_login_logout_redirect(
        notice='account-deleted',
        id_token='id-token-value',
    )
    assert response.status_code == 302
    location = response.headers['location']
    frontend = configuration.keycloak.frontend_url.rstrip('/')
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    post_logout = query.get(
        'post_logout_redirect_uri',
        [''],
    )[0]
    assert post_logout == frontend
    assert 'notice=' not in post_logout
    assert query.get('id_token_hint') == ['id-token-value']
    cookies = response.headers.getlist('set-cookie')
    notice_cookie = next(
        (
            item
            for item in cookies
            if LOGIN_NOTICE_COOKIE in item
        ),
        '',
    )
    assert 'account-deleted' in notice_cookie


@pytest.mark.asyncio
async def test_login_callback_deleted_account_no_auth_cookies():
    request = MagicMock()
    request.cookies = {}
    keycloak = AsyncMock()
    keycloak.get_tokens = AsyncMock(
        return_value={
            'access_token': 'access',
            'refresh_token': 'refresh',
            'id_token': 'idtok',
        },
    )
    message_bus = AsyncMock()

    with patch.object(
        auth_router.KeycloakClient,
        'resolve_redirect_uri',
        return_value='http://example/callback',
    ), patch.object(
        auth_router,
        '_persist_user_from_tokens',
        new_callable=AsyncMock,
        side_effect=AccountDeletedError(),
    ), patch.object(
        auth_router,
        'resolve_client_ip',
        new_callable=AsyncMock,
        return_value='1.2.3.4',
    ), patch.object(
        auth_router,
        'set_auth_cookies',
    ) as set_cookies, patch.object(
        auth_router,
        'read_anon_id',
        return_value=None,
    ):
        response = await auth_router.login_callback(
            request=request,
            code='auth-code',
            state=None,
            keycloak=keycloak,
            message_bus=message_bus,
        )

    assert response.status_code == 302
    location = unquote(response.headers['location'])
    frontend = configuration.keycloak.frontend_url.rstrip('/')
    assert f'post_logout_redirect_uri={frontend}' in location
    assert 'notice=account-deleted' not in location
    set_cookies.assert_not_called()
    cookies = response.headers.getlist('set-cookie')
    assert any(
        LOGIN_NOTICE_COOKIE in item
        and 'account-deleted' in item
        for item in cookies
    )
