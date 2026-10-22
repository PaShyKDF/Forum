"""Handlers управления ACL и видимостью."""

from general.logger import log, logger

from forum.domain import commands
from forum.domain.exceptions import EntityNotFoundError
from forum.domain.schemas.topics import AccessMemberResponse
from forum.domain.schemas.users import UserResponse
from forum.service_layer import unit_of_work
from forum.service_layer.access_control import require_admin
from forum.service_layer.assemblers import build_user_response


def _member_response(user) -> AccessMemberResponse:
    """
    Собирает DTO участника ACL из ORM User.

    Args:
        user: Модель пользователя с полями профиля.

    Returns:
        AccessMemberResponse для API ACL.
    """
    return AccessMemberResponse(
        uid=user.uid,
        username=user.username,
        display_name=user.display_name,
        initials=user.initials,
        avatar_url=(
            f'/api/users/{user.uid}/avatar'
            if user.avatar_mime
            else user.avatar_url
        ),
    )


@log
async def handle_get_category_members_command(
    command: commands.GetCategoryMembersCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> list[AccessMemberResponse]:
    """
    Список пользователей в ACL категории.

    Args:
        command: ID категории и флаг is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        Участники whitelist категории.

    Raises:
        PermissionDeniedError: Если вызывающий не админ.
        EntityNotFoundError: Если категория не найдена.
    """
    require_admin(command.is_admin)
    category = await uow.category_repository.get_by_id(
        command.category_id,
    )
    if category is None:
        raise EntityNotFoundError(
            'Category',
            command.category_id,
        )
    users = await uow.content_acl_repository.list_category_users(
        command.category_id,
    )
    return [_member_response(user) for user in users]


@log
async def handle_get_topic_members_command(
    command: commands.GetTopicMembersCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> list[AccessMemberResponse]:
    """
    Список пользователей в ACL темы.

    Args:
        command: ID темы и флаг is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        Участники whitelist темы.

    Raises:
        PermissionDeniedError: Если вызывающий не админ.
        EntityNotFoundError: Если тема не найдена.
    """
    require_admin(command.is_admin)
    topic = await uow.topic_repository.get_by_id(
        command.topic_id,
    )
    if topic is None:
        raise EntityNotFoundError('Topic', command.topic_id)
    users = await uow.content_acl_repository.list_topic_users(
        command.topic_id,
    )
    return [_member_response(user) for user in users]


@log
async def handle_set_category_members_command(
    command: commands.SetCategoryMembersCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> list[AccessMemberResponse]:
    """
    Заменяет whitelist пользователей категории.

    Args:
        command: ID категории, список uid, is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        Актуальный список участников после сохранения.

    Raises:
        PermissionDeniedError: Если вызывающий не админ.
        EntityNotFoundError: Если категория не найдена.
    """
    require_admin(command.is_admin)
    category = await uow.category_repository.get_by_id(
        command.category_id,
    )
    if category is None:
        raise EntityNotFoundError(
            'Category',
            command.category_id,
        )
    await uow.content_acl_repository.set_category_users(
        command.category_id,
        command.user_uids,
    )
    await uow.commit()
    users = await uow.content_acl_repository.list_category_users(
        command.category_id,
    )
    logger.info(
        'ACL категории %s: %s пользователей',
        command.category_id,
        len(users),
    )
    return [_member_response(user) for user in users]


@log
async def handle_set_topic_members_command(
    command: commands.SetTopicMembersCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> list[AccessMemberResponse]:
    """
    Заменяет whitelist пользователей темы.

    Args:
        command: ID темы, список uid, is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        Актуальный список участников после сохранения.

    Raises:
        PermissionDeniedError: Если вызывающий не админ.
        EntityNotFoundError: Если тема не найдена.
    """
    require_admin(command.is_admin)
    topic = await uow.topic_repository.get_by_id(
        command.topic_id,
    )
    if topic is None:
        raise EntityNotFoundError('Topic', command.topic_id)
    await uow.content_acl_repository.set_topic_users(
        command.topic_id,
        command.user_uids,
    )
    await uow.commit()
    users = await uow.content_acl_repository.list_topic_users(
        command.topic_id,
    )
    logger.info(
        'ACL темы %s: %s пользователей',
        command.topic_id,
        len(users),
    )
    return [_member_response(user) for user in users]


@log
async def handle_set_category_visibility_command(
    command: commands.SetCategoryVisibilityCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> dict:
    """
    Включает или выключает ограничение категории.

    ACL-список при открытии не очищается — нужен
    для повторного скрытия.

    Args:
        command: ID категории, is_restricted, is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        Словарь с id и is_restricted категории.

    Raises:
        PermissionDeniedError: Если вызывающий не админ.
        EntityNotFoundError: Если категория не найдена.
    """
    require_admin(command.is_admin)
    category = await uow.category_repository.get_by_id(
        command.category_id,
    )
    if category is None:
        raise EntityNotFoundError(
            'Category',
            command.category_id,
        )
    category.is_restricted = command.is_restricted
    # ACL не очищаем при открытии — нужен для повторного скрытия
    await uow.commit()
    logger.info(
        'Категория %s is_restricted=%s',
        command.category_id,
        command.is_restricted,
    )
    return {
        'id': category.id,
        'is_restricted': category.is_restricted,
    }


@log
async def handle_set_topic_visibility_command(
    command: commands.SetTopicVisibilityCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> dict:
    """
    Включает или выключает ограничение темы.

    Args:
        command: ID темы, is_restricted, is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        Словарь с id и is_restricted темы.

    Raises:
        PermissionDeniedError: Если вызывающий не админ.
        EntityNotFoundError: Если тема не найдена.
    """
    require_admin(command.is_admin)
    topic = await uow.topic_repository.get_by_id(
        command.topic_id,
    )
    if topic is None:
        raise EntityNotFoundError('Topic', command.topic_id)
    topic.is_restricted = command.is_restricted
    await uow.commit()
    logger.info(
        'Тема %s is_restricted=%s',
        command.topic_id,
        command.is_restricted,
    )
    return {
        'id': topic.id,
        'is_restricted': topic.is_restricted,
    }


@log
async def handle_search_users_command(
    command: commands.SearchUsersCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> list[UserResponse]:
    """
    Поиск зарегистрированных пользователей для ACL UI.

    Args:
        command: Строка query, limit, is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        Список UserResponse по запросу.

    Raises:
        PermissionDeniedError: Если вызывающий не админ.
    """
    require_admin(command.is_admin)
    users = await uow.user_repository.search_registered(
        command.query,
        limit=command.limit,
    )
    return [build_user_response(user) for user in users]
