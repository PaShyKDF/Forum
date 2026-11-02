"""Обезличивание удалённых пользователей."""

import uuid

from forum.domain.models import User


DELETED_USER_DISPLAY_NAME = 'Пользователь удален'
DELETED_USER_INITIALS = '?'


def is_user_deleted(user: User | None) -> bool:
    """
    Проверяет флаг is_deleted у пользователя.

    Args:
        user: ORM User или None.

    Returns:
        True, если пользователь обезличен.
    """
    if user is None:
        return False
    return bool(getattr(user, 'is_deleted', False))


def public_display_name(user: User) -> str:
    """
    Публичное имя для форума.

    Args:
        user: ORM User.

    Returns:
        «Пользователь удален» или display_name.
    """
    if is_user_deleted(user):
        return DELETED_USER_DISPLAY_NAME
    return user.display_name


def public_initials(user: User) -> str:
    """
    Инициалы для аватара-заглушки.

    Args:
        user: ORM User.

    Returns:
        '?' для удалённого, иначе initials.
    """
    if is_user_deleted(user):
        return DELETED_USER_INITIALS
    return user.initials


def anonymize_user(user: User) -> None:
    """
    Обезличивает пользователя in-place.

    Сохраняет email и last_ip для бана повторной
    регистрации. Сбрасывает аватар и anon_id.
    Не коммитит сессию.

    Args:
        user: ORM User для обезличивания.
    """
    user.is_deleted = True
    user.is_active = False
    user.display_name = DELETED_USER_DISPLAY_NAME
    user.initials = DELETED_USER_INITIALS
    user.username = f'deleted-{user.uid}'
    user.email_verified = False
    user.avatar_url = None
    user.avatar_mime = None
    user.avatar_blob = None
    user.anon_id = None
    user.is_guest = False


def admin_uid_from_request_token(
    token: str | None,
) -> uuid.UUID | None:
    """
    Достаёт Keycloak sub из access_token админа.

    Args:
        token: JWT или None.

    Returns:
        UUID sub или None.
    """
    if not token:
        return None
    from forum.service_layer.keycloak_client import (
        KeycloakClient,
    )

    try:
        payload = KeycloakClient.decode_token_payload(token)
    except Exception:
        return None
    sub = payload.get('sub')
    if not sub:
        return None
    try:
        return uuid.UUID(str(sub))
    except ValueError:
        return None
