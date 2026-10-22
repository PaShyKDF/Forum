"""Handlers профиля пользователя."""

from general.logger import log

from forum.domain import commands
from forum.domain.exceptions import DomainError, EntityNotFoundError
from forum.domain.schemas.users import (
    PublicUserProfileResponse,
    UserProfileResponse,
)
from forum.service_layer import unit_of_work
from forum.service_layer.assemblers import (
    build_public_user_profile_response,
    build_user_profile_response,
)
from forum.service_layer.handlers.auth import make_initials


@log
async def handle_get_current_user_profile_command(
    command: commands.GetCurrentUserProfileCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> UserProfileResponse:
    """
    Профиль пользователя и число активных сообщений.

    Args:
        command: uid текущего пользователя.
        uow: Unit of Work текущего запроса.

    Returns:
        UserProfileResponse с числом сообщений.

    Raises:
        EntityNotFoundError: Если пользователь не найден.
    """
    user = await uow.user_repository.get_by_id(command.user_uid)
    if user is None:
        raise EntityNotFoundError('User', command.user_uid)

    posts_count = await uow.post_repository.count_by_author(
        command.user_uid,
    )
    return build_user_profile_response(user, posts_count)


@log
async def handle_get_public_user_profile_command(
    command: commands.GetPublicUserProfileCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> PublicUserProfileResponse:
    """
    Публичный профиль пользователя со статистикой.

    Args:
        command: uid пользователя профиля.
        uow: Unit of Work текущего запроса.

    Returns:
        PublicUserProfileResponse с posts_count и
        topics_count.

    Raises:
        EntityNotFoundError: Если пользователь не найден.
    """
    user = await uow.user_repository.get_by_id(command.user_uid)
    if user is None:
        raise EntityNotFoundError('User', command.user_uid)

    posts_count = await uow.post_repository.count_by_author(
        command.user_uid,
    )
    topics_count = await uow.topic_repository.count_by_author(
        command.user_uid,
    )
    return build_public_user_profile_response(
        user,
        posts_count=posts_count,
        topics_count=topics_count,
    )


@log
async def handle_update_user_profile_command(
    command: commands.UpdateUserProfileCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> UserProfileResponse:
    """
    Обновляет display_name и инициалы.

    Args:
        command: uid и новый никнейм.
        uow: Unit of Work текущего запроса.

    Returns:
        UserProfileResponse после сохранения.

    Raises:
        DomainError: Если никнейм пустой.
        EntityNotFoundError: Если пользователь не найден.
    """
    display_name = command.display_name.strip()
    if not display_name:
        raise DomainError(
            'Никнейм не может быть пустым',
            'EMPTY_DISPLAY_NAME',
        )

    user = await uow.user_repository.update_display_name(
        command.user_uid,
        display_name,
        make_initials(display_name),
    )
    if user is None:
        raise EntityNotFoundError('User', command.user_uid)

    await uow.commit()
    posts_count = await uow.post_repository.count_by_author(
        command.user_uid,
    )
    return build_user_profile_response(user, posts_count)


@log
async def handle_upload_user_avatar_command(
    command: commands.UploadUserAvatarCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> UserProfileResponse:
    """
    Сохраняет фото аватара в PostgreSQL.

    Args:
        command: uid, байты аватара и MIME-тип.
        uow: Unit of Work текущего запроса.

    Returns:
        UserProfileResponse после сохранения.

    Raises:
        EntityNotFoundError: Если пользователь не найден.
    """
    user = await uow.user_repository.update_avatar_blob(
        command.user_uid,
        command.content,
        command.mime_type,
    )
    if user is None:
        raise EntityNotFoundError('User', command.user_uid)

    await uow.commit()
    posts_count = await uow.post_repository.count_by_author(
        command.user_uid,
    )
    return build_user_profile_response(user, posts_count)


@log
async def handle_delete_user_avatar_command(
    command: commands.DeleteUserAvatarCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> UserProfileResponse:
    """
    Удаляет фото аватара.

    Args:
        command: uid пользователя.
        uow: Unit of Work текущего запроса.

    Returns:
        UserProfileResponse после удаления.

    Raises:
        EntityNotFoundError: Если пользователь не найден.
    """
    user = await uow.user_repository.clear_avatar(
        command.user_uid,
    )
    if user is None:
        raise EntityNotFoundError('User', command.user_uid)

    await uow.commit()
    posts_count = await uow.post_repository.count_by_author(
        command.user_uid,
    )
    return build_user_profile_response(user, posts_count)


@log
async def handle_get_user_avatar_command(
    command: commands.GetUserAvatarCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> tuple[bytes, str]:
    """
    Возвращает байты и MIME аватара.

    Args:
        command: uid пользователя.
        uow: Unit of Work текущего запроса.

    Returns:
        Кортеж (content, mime_type).

    Raises:
        EntityNotFoundError: Если пользователь или фото
            не найдены.
    """
    user = await uow.user_repository.get_with_avatar(
        command.user_uid,
    )
    if user is None or user.avatar_blob is None:
        raise EntityNotFoundError('Avatar', command.user_uid)
    mime = user.avatar_mime or 'application/octet-stream'
    return user.avatar_blob, mime
