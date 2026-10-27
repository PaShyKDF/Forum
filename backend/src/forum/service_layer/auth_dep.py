"""Зависимости FastAPI для авторизации."""

from fastapi import Depends, HTTPException, Request, Response

from forum.config import configuration
from forum.domain.schemas.users import UserResponse
from forum.service_layer.auth_cookies import (
    refresh_session_if_needed,
)
from forum.service_layer.client_ip import resolve_client_ip
from forum.service_layer.handlers.auth import (
    ensure_user_command_from_keycloak,
)
from forum.service_layer.handlers.visitors import (
    finalize_guest_cookie_after_login,
)
from forum.service_layer.keycloak_client import KeycloakClient
from forum.service_layer.messagebus import (
    MessageBus,
    get_message_bus,
)
from forum.service_layer.visitor_cookies import read_anon_id


def token_is_admin(token: str | None) -> bool:
    """
    Проверяет, есть ли у access_token роль админа форума.

    Args:
        token: JWT доступа Keycloak или None.

    Returns:
        True, если в токене есть required_role админа.
    """
    if not token:
        return False
    return KeycloakClient.has_role(
        token,
        configuration.admin.required_role,
    )


def get_keycloak_client(request: Request) -> KeycloakClient:
    """
    Достаёт KeycloakClient из состояния FastAPI-приложения.

    Клиент создаётся в lifespan и живёт на общем
    httpx.AsyncClient.

    Args:
        request: текущий HTTP-запрос FastAPI.

    Returns:
        Экземпляр KeycloakClient из app.state.
    """
    return request.app.state.keycloak_client


async def get_token_from_cookie(
    request: Request,
    response: Response,
    keycloak: KeycloakClient = Depends(get_keycloak_client),
) -> str | None:
    """
    Читает access_token из cookie, при истечении — refresh.

    Args:
        request: текущий HTTP-запрос.
        response: ответ для обновления auth-cookies.
        keycloak: клиент Keycloak.

    Returns:
        Валидный JWT или None.
    """
    return await refresh_session_if_needed(
        request,
        response,
        keycloak,
    )


async def _user_info_from_token(
    token: str,
    keycloak: KeycloakClient,
    request: Request,
) -> dict:
    """Профиль пользователя по access_token / id_token."""
    id_token = request.cookies.get('id_token')
    try:
        if id_token and not KeycloakClient.is_token_expired(
            id_token,
        ):
            return KeycloakClient.user_info_from_id_token(
                id_token,
            )
        return await keycloak.get_user_info(token)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail='Invalid token',
        ) from exc


async def get_current_user(
    request: Request,
    response: Response,
    token: str | None = Depends(get_token_from_cookie),
    keycloak: KeycloakClient = Depends(get_keycloak_client),
    message_bus: MessageBus = Depends(get_message_bus),
) -> UserResponse:
    """
    Текущий пользователь форума (обязательная авторизация).

    Читает cookie, upsert'ит пользователя в БД и возвращает
    UserResponse. При наличии anon_id делает merge/удаление
    stale-гостя и чистит guest cookie.

    Args:
        request: текущий HTTP-запрос.
        response: ответ для очистки guest cookie.
        token: валидный access JWT или None.
        keycloak: клиент Keycloak.
        message_bus: шина команд/событий.

    Returns:
        UserResponse с флагом is_admin.

    Raises:
        HTTPException: 401, если токена нет или он невалиден.
    """
    if not token:
        raise HTTPException(
            status_code=401,
            detail='Не авторизован',
        )

    user_info = await _user_info_from_token(
        token,
        keycloak,
        request,
    )
    try:
        command = ensure_user_command_from_keycloak(
            user_info,
            anon_id=read_anon_id(request),
            client_ip=await resolve_client_ip(request),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc
    user = await message_bus.handle(command)
    finalize_guest_cookie_after_login(response)
    user.is_admin = token_is_admin(token)
    return user


async def get_optional_current_user(
    request: Request,
    response: Response,
    token: str | None = Depends(get_token_from_cookie),
    keycloak: KeycloakClient = Depends(get_keycloak_client),
    message_bus: MessageBus = Depends(get_message_bus),
) -> UserResponse | None:
    """
    Текущий пользователь форума или None для гостя.

    При ошибке авторизации не бросает 401, а возвращает None.

    Args:
        request: текущий HTTP-запрос.
        response: ответ для обновления cookies.
        token: валидный access JWT или None.
        keycloak: клиент Keycloak.
        message_bus: шина команд/событий.

    Returns:
        UserResponse или None.
    """
    if not token:
        return None
    try:
        return await get_current_user(
            request=request,
            response=response,
            token=token,
            keycloak=keycloak,
            message_bus=message_bus,
        )
    except HTTPException:
        return None


async def get_forum_admin(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """
    Требует, чтобы текущий пользователь был админом форума.

    Args:
        current_user: авторизованный пользователь.

    Returns:
        Тот же UserResponse, если is_admin=True.

    Raises:
        HTTPException: 403 при недостаточных правах.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail='Недостаточно прав',
        )
    return current_user
