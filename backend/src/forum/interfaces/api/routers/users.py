"""API профиля текущего пользователя."""

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse

from forum.domain import commands
from forum.domain.exceptions import DomainError
from forum.domain.schemas.users import (
    ChangePasswordUrlResponse,
    PublicUserProfileResponse,
    UpdateUserProfileRequest,
    UserProfileResponse,
    UserResponse,
)
from forum.interfaces.api.error_mapping import (
    raise_http_from_domain,
)
from forum.service_layer.auth_cookies import (
    set_post_login_next_cookie,
)
from forum.service_layer.auth_dep import (
    get_current_user,
    get_forum_admin,
)
from forum.service_layer.keycloak_client import KeycloakClient
from forum.service_layer.messagebus import MessageBus, get_message_bus


router = APIRouter(
    prefix='/users',
    tags=['users'],
)

_ALLOWED_AVATAR_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
}
_MAX_AVATAR_BYTES = 2 * 1024 * 1024


@router.get(
    '/search',
    response_model=list[UserResponse],
    summary='Поиск пользователей (админ)',
)
async def search_users(
    q: str = Query('', description='Строка поиска'),
    limit: int = Query(20, ge=1, le=50),
    current_user: UserResponse = Depends(get_forum_admin),
    message_bus: MessageBus = Depends(get_message_bus),
) -> list[UserResponse]:
    """
    Ищет пользователей по строке (только админ).

    Args:
        q: подстрока поиска.
        limit: максимум результатов (1–50).
        current_user: администратор форума.
        message_bus: Depends MessageBus.

    Returns:
        Список UserResponse.

    Raises:
        HTTPException: при доменной ошибке.
    """
    try:
        return await message_bus.handle(
            commands.SearchUsersCommand(
                query=q,
                limit=limit,
                is_admin=True,
            ),
        )
    except DomainError as error:
        raise_http_from_domain(error)


@router.get(
    '/me',
    response_model=UserProfileResponse,
    summary='Профиль текущего пользователя',
)
async def get_current_user_profile(
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> UserProfileResponse:
    """
    Возвращает полный профиль текущего пользователя.

    Args:
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        UserProfileResponse.

    Raises:
        HTTPException: при доменной ошибке наличия.
    """
    command = commands.GetCurrentUserProfileCommand(
        user_uid=current_user.uid,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.get(
    '/{user_uid}',
    response_model=PublicUserProfileResponse,
    summary='Публичный профиль пользователя',
)
async def get_public_user_profile(
    user_uid: uuid.UUID,
    message_bus: MessageBus = Depends(get_message_bus),
) -> PublicUserProfileResponse:
    """
    Возвращает публичный профиль пользователя по uid.

    Args:
        user_uid: UUID пользователя.
        message_bus: Depends MessageBus.

    Returns:
        PublicUserProfileResponse.

    Raises:
        HTTPException: 404 если пользователь не найден.
    """
    command = commands.GetPublicUserProfileCommand(
        user_uid=user_uid,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.patch(
    '/me',
    response_model=UserProfileResponse,
    summary='Обновить профиль',
    description='Обновляет никнейм (display_name).',
)
async def update_current_user_profile(
    payload: UpdateUserProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> UserProfileResponse:
    """
    Обновляет никнейм (display_name) текущего пользователя.

    Args:
        payload: поля профиля (display_name обязателен).
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        UserProfileResponse после обновления.

    Raises:
        HTTPException: 422 без display_name; иначе доменные.
    """
    if payload.display_name is None:
        raise HTTPException(
            status_code=422,
            detail='Укажите display_name',
        )
    command = commands.UpdateUserProfileCommand(
        user_uid=current_user.uid,
        display_name=payload.display_name,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.post(
    '/me/avatar',
    response_model=UserProfileResponse,
    summary='Загрузить фото профиля',
)
async def upload_current_user_avatar(
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> UserProfileResponse:
    """
    Загружает аватар текущего пользователя (JPEG/PNG/WebP).

    Args:
        file: файл изображения (не больше 2 МБ).
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        UserProfileResponse с новым URL аватара.

    Raises:
        HTTPException: 422 при неверном типе/размере/пустоте.
    """
    mime = (file.content_type or '').lower()
    if mime not in _ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                'Допустимы только JPEG, PNG или WebP'
            ),
        )
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=422,
            detail='Файл пустой',
        )
    if len(content) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=422,
            detail='Размер файла не больше 2 МБ',
        )
    command = commands.UploadUserAvatarCommand(
        user_uid=current_user.uid,
        content=content,
        mime_type=mime,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.delete(
    '/me/avatar',
    response_model=UserProfileResponse,
    summary='Удалить фото профиля',
)
async def delete_current_user_avatar(
    current_user: UserResponse = Depends(get_current_user),
    message_bus: MessageBus = Depends(get_message_bus),
) -> UserProfileResponse:
    """
    Удаляет аватар текущего пользователя.

    Args:
        current_user: авторизованный пользователь.
        message_bus: Depends MessageBus.

    Returns:
        UserProfileResponse без аватара.

    Raises:
        HTTPException: при доменной ошибке.
    """
    command = commands.DeleteUserAvatarCommand(
        user_uid=current_user.uid,
    )
    try:
        return await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)


@router.get(
    '/{user_uid}/avatar',
    summary='Фото пользователя',
    response_class=Response,
)
async def get_user_avatar(
    user_uid: uuid.UUID,
    message_bus: MessageBus = Depends(get_message_bus),
) -> Response:
    """
    Отдаёт байты аватара пользователя с Cache-Control.

    Args:
        user_uid: UUID владельца аватара.
        message_bus: Depends MessageBus.

    Returns:
        Response с телом изображения и media_type.

    Raises:
        HTTPException: 404 если аватар не найден.
    """
    command = commands.GetUserAvatarCommand(user_uid=user_uid)
    try:
        content, mime = await message_bus.handle(command)
    except DomainError as error:
        raise_http_from_domain(error)
    return Response(
        content=content,
        media_type=mime,
        headers={
            'Cache-Control': 'public, max-age=3600',
        },
    )


@router.get(
    '/me/change-password-url',
    response_model=ChangePasswordUrlResponse,
    summary='URL смены пароля в Keycloak',
)
async def get_change_password_url(
    _current_user: UserResponse = Depends(get_current_user),
) -> JSONResponse:
    """
    Возвращает OIDC URL с kc_action=UPDATE_PASSWORD.

    Ставит cookie next=#/, чтобы после отмены/успеха
    callback вернул пользователя на главную форума.

    Args:
        _current_user: авторизованный пользователь.

    Returns:
        JSONResponse с полем url и Set-Cookie next.
    """
    url = KeycloakClient.build_auth_url(
        kc_action='UPDATE_PASSWORD',
    )
    payload = ChangePasswordUrlResponse(url=url)
    response = JSONResponse(content=payload.model_dump())
    set_post_login_next_cookie(response, '#/')
    return response
