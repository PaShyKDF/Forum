"""Установка и очистка auth-cookies (OIDC-токены)."""

import logging

from fastapi import HTTPException, Request, Response

from forum.config import configuration
from forum.service_layer.keycloak_client import KeycloakClient


logger = logging.getLogger(__name__)

POST_LOGIN_NEXT_COOKIE = 'post_login_next'
_MAX_NEXT_LENGTH = 500


def sanitize_post_login_next(raw: str | None) -> str | None:
    """
    Проверяет next-URL для редиректа после логина.

    Разрешены только SPA-пути вида #/… (без внешних URL).

    Args:
        raw: значение query/cookie next.

    Returns:
        Нормализованный hash-путь или None.
    """
    if not raw:
        return None
    value = raw.strip()
    if not value or len(value) > _MAX_NEXT_LENGTH:
        return None
    if (
        '://' in value
        or '//' in value
        or '\n' in value
        or '\r' in value
    ):
        return None
    if value.startswith('/#/'):
        value = value[1:]
    elif value.startswith('/'):
        value = f'#{value}'
    elif not value.startswith('#'):
        value = f'#/{value.lstrip("/")}'
    if not value.startswith('#/'):
        return None
    if value == '#/login' or value.startswith('#/login?'):
        return '#/'
    return value


def build_post_login_url(next_path: str | None = None) -> str:
    """
    Абсолютный URL фронта после успешного входа.

    Args:
        next_path: безопасный hash-путь (#/topic/1) или None.

    Returns:
        URL на frontend (по умолчанию главная).
    """
    base = configuration.keycloak.frontend_url.rstrip('/')
    safe = sanitize_post_login_next(next_path)
    if safe:
        return f'{base}/{safe}'
    return configuration.keycloak.post_login_redirect


def set_post_login_next_cookie(
    response: Response,
    next_path: str,
) -> None:
    """
    Сохраняет путь возврата на время OIDC-логина.

    Args:
        response: HTTP-ответ с Set-Cookie.
        next_path: безопасный hash-путь (#/topic/1).
    """
    response.set_cookie(
        key=POST_LOGIN_NEXT_COOKIE,
        value=next_path,
        httponly=True,
        secure=configuration.keycloak.cookie_secure,
        samesite='lax',
        path='/',
        max_age=600,
    )


def clear_post_login_next_cookie(response: Response) -> None:
    """
    Удаляет cookie пути возврата после логина.

    Args:
        response: HTTP-ответ с Delete-Cookie.
    """
    response.delete_cookie(
        key=POST_LOGIN_NEXT_COOKIE,
        httponly=True,
        secure=configuration.keycloak.cookie_secure,
        samesite='lax',
        path='/',
    )


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    id_token: str,
    token_data: dict,
) -> None:
    """
    Кладёт OIDC-токены в HttpOnly-cookies ответа.

    Имена cookies: access_token, refresh_token, id_token.
    Флаг Secure берётся из configuration.keycloak.cookie_secure
    (True только для https frontend_url). max_age — из
    expires_in / refresh_expires_in ответа token endpoint.

    Args:
        response: HTTP-ответ, в который пишутся Set-Cookie.
        access_token: JWT доступа Keycloak.
        refresh_token: refresh JWT Keycloak.
        id_token: OIDC id_token (нужен для logout hint).
        token_data: сырой JSON token endpoint (expires_in и т.п.).
    """
    secure = configuration.keycloak.cookie_secure
    response.set_cookie(
        key='access_token',
        value=access_token,
        httponly=True,
        secure=secure,
        samesite='lax',
        path='/',
        max_age=token_data.get('expires_in', 3600),
    )
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite='lax',
        path='/',
        max_age=token_data.get(
            'refresh_expires_in',
            2592000,
        ),
    )
    # id_token нужен для logout hint — живёт вместе с refresh
    response.set_cookie(
        key='id_token',
        value=id_token,
        httponly=True,
        secure=secure,
        samesite='lax',
        path='/',
        max_age=token_data.get(
            'refresh_expires_in',
            token_data.get('expires_in', 3600),
        ),
    )


def clear_auth_cookies(response: Response) -> None:
    """
    Удаляет auth-cookies с теми же атрибутами, что при set.

    Args:
        response: HTTP-ответ с Delete-Cookie.
    """
    secure = configuration.keycloak.cookie_secure
    for name in (
        'access_token',
        'refresh_token',
        'id_token',
    ):
        response.delete_cookie(
            key=name,
            httponly=True,
            secure=secure,
            samesite='lax',
            path='/',
        )


async def refresh_session_if_needed(
    request: Request,
    response: Response,
    keycloak: KeycloakClient,
) -> str | None:
    """
    Возвращает валидный access_token, при необходимости
    обновляя сессию через refresh_token.

    Если access ещё жив — возвращает его. Если истёк
    (или отсутствует), а refresh есть — обменивает токены
    и обновляет cookies. При ошибке refresh чистит cookies.

    Args:
        request: HTTP-запрос с auth-cookies.
        response: ответ для Set-Cookie / Delete-Cookie.
        keycloak: клиент Keycloak.

    Returns:
        Валидный access_token или None.
    """
    access_token = request.cookies.get('access_token')
    refresh_token = request.cookies.get('refresh_token')

    if access_token and not KeycloakClient.is_token_expired(
        access_token,
    ):
        return access_token

    if not refresh_token:
        if access_token:
            clear_auth_cookies(response)
        return None

    try:
        token_data = await keycloak.refresh_tokens(
            refresh_token,
        )
    except HTTPException as exc:
        logger.warning(
            'Refresh session failed: %s',
            exc.detail,
        )
        clear_auth_cookies(response)
        return None
    except Exception:
        logger.exception('Refresh session unexpected error')
        clear_auth_cookies(response)
        return None

    new_access = token_data.get('access_token')
    new_refresh = (
        token_data.get('refresh_token') or refresh_token
    )
    new_id = (
        token_data.get('id_token')
        or request.cookies.get('id_token')
    )
    if not new_access or not new_id:
        logger.error(
            'Refresh response without access/id token',
        )
        clear_auth_cookies(response)
        return None

    set_auth_cookies(
        response,
        access_token=new_access,
        refresh_token=new_refresh,
        id_token=new_id,
        token_data=token_data,
    )
    return new_access
