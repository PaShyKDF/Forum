"""Cookie для анонимных посетителей (forum_anon_id)."""

import re
import uuid

from fastapi import Request, Response

from forum.config import configuration


ANON_COOKIE_NAME = 'forum_anon_id'
_ANON_ID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
    r'[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def new_anon_id() -> str:
    """
    Генерирует новый UUID для гостевой cookie.

    Returns:
        Строка UUID в нижнем регистре.
    """
    return str(uuid.uuid4())


def read_anon_id(request: Request) -> str | None:
    """
    Читает и валидирует forum_anon_id из cookies.

    Args:
        request: HTTP-запрос с cookies.

    Returns:
        Нормализованный UUID или None.
    """
    raw = request.cookies.get(ANON_COOKIE_NAME)
    if not raw:
        return None
    value = raw.strip()
    if not _ANON_ID_RE.match(value):
        return None
    return value.lower()


def set_anon_cookie(response: Response, anon_id: str) -> None:
    """
    Ставит HttpOnly cookie forum_anon_id.

    Args:
        response: HTTP-ответ с Set-Cookie.
        anon_id: валидный UUID гостя.
    """
    response.set_cookie(
        key=ANON_COOKIE_NAME,
        value=anon_id,
        httponly=True,
        secure=configuration.keycloak.cookie_secure,
        samesite='lax',
        path='/',
        max_age=configuration.visitors.anon_cookie_max_age,
    )


def clear_anon_cookie(response: Response) -> None:
    """
    Удаляет forum_anon_id после merge в аккаунт.

    Args:
        response: HTTP-ответ с Delete-Cookie.
    """
    response.delete_cookie(
        key=ANON_COOKIE_NAME,
        httponly=True,
        secure=configuration.keycloak.cookie_secure,
        samesite='lax',
        path='/',
    )
