"""Проверки доступа к категориям и темам."""

import uuid

from forum.domain.exceptions import (
    EntityNotFoundError,
    PermissionDeniedError,
)
from forum.domain.models import Category, Topic
from forum.service_layer import unit_of_work


async def can_read_category(
    uow: unit_of_work.AbstractUnitOfWork,
    category: Category,
    *,
    user_uid: uuid.UUID | None,
    is_admin: bool = False,
) -> bool:
    """
    Проверяет, видна ли категория пользователю.

    Админ видит всё. Открытая категория видна всем.
    Скрытая — по ACL категории или любой темы внутри.

    Args:
        uow: Unit of Work с репозиторием ACL.
        category: Загруженная модель категории.
        user_uid: UID текущего пользователя или None
            для гостя.
        is_admin: True, если роль форум-админа.

    Returns:
        True, если категорию можно показать.
    """
    if not category.is_active:
        return False
    if is_admin:
        return True
    if not category.is_restricted:
        return True
    if user_uid is None:
        return False
    if await uow.content_acl_repository.user_has_category_access(
        category.id,
        user_uid,
    ):
        return True
    return await (
        uow.content_acl_repository
        .user_has_any_topic_access_in_category(
            category.id,
            user_uid,
        )
    )


async def can_read_topic(
    uow: unit_of_work.AbstractUnitOfWork,
    topic: Topic,
    category: Category | None = None,
    *,
    user_uid: uuid.UUID | None,
    is_admin: bool = False,
) -> bool:
    """
    Проверяет, видна ли тема пользователю.

    Учитывает is_restricted категории и темы, а также
    personal whitelist (topic ACL vs category ACL).

    Args:
        uow: Unit of Work с репозиториями.
        topic: Загруженная модель темы.
        category: Родительская категория, если уже
            известна (избегает lazy-load).
        user_uid: UID текущего пользователя или None.
        is_admin: True, если роль форум-админа.

    Returns:
        True, если тему можно показать.
    """
    if not topic.is_active:
        return False
    if is_admin:
        return True

    parent = category
    if parent is None:
        parent = await uow.category_repository.get_active_by_id(
            topic.category_id,
        )
    if parent is None or not parent.is_active:
        return False

    has_category_acl = False
    has_topic_acl = False
    has_any_topic_acl = False
    if user_uid is not None:
        has_category_acl = await (
            uow.content_acl_repository.user_has_category_access(
                parent.id,
                user_uid,
            )
        )
        has_topic_acl = await (
            uow.content_acl_repository.user_has_topic_access(
                topic.id,
                user_uid,
            )
        )
        has_any_topic_acl = await (
            uow.content_acl_repository
            .user_has_any_topic_access_in_category(
                parent.id,
                user_uid,
            )
        )

    # Скрытая категория:
    # - только category ACL → все темы;
    # - есть topic ACL (даже вместе с category) → только
    #   темы из personal whitelist.
    if parent.is_restricted:
        if has_any_topic_acl:
            return has_topic_acl
        return has_category_acl

    # Открытая категория: скрытая тема — по whitelist.
    if not topic.is_restricted:
        return True
    return has_topic_acl


async def require_category_read(
    uow: unit_of_work.AbstractUnitOfWork,
    category_id: int,
    *,
    user_uid: uuid.UUID | None,
    is_admin: bool = False,
) -> Category:
    """
    Загружает активную категорию с проверкой доступа.

    При отказе в доступе маскирует 403 как 404.

    Args:
        uow: Unit of Work текущего запроса.
        category_id: ID категории.
        user_uid: UID пользователя или None.
        is_admin: True для форум-админа.

    Returns:
        Активная Category, доступная вызывающему.

    Raises:
        EntityNotFoundError: Нет категории или нет доступа.
    """
    category = await uow.category_repository.get_active_by_id(
        category_id,
    )
    if category is None:
        raise EntityNotFoundError('Category', category_id)
    allowed = await can_read_category(
        uow,
        category,
        user_uid=user_uid,
        is_admin=is_admin,
    )
    if not allowed:
        raise EntityNotFoundError('Category', category_id)
    return category


async def require_topic_read(
    uow: unit_of_work.AbstractUnitOfWork,
    topic_id: int,
    *,
    user_uid: uuid.UUID | None,
    is_admin: bool = False,
) -> Topic:
    """
    Загружает активную тему с проверкой доступа.

    При отказе в доступе маскирует 403 как 404.

    Args:
        uow: Unit of Work текущего запроса.
        topic_id: ID темы.
        user_uid: UID пользователя или None.
        is_admin: True для форум-админа.

    Returns:
        Активная Topic, доступная вызывающему.

    Raises:
        EntityNotFoundError: Нет темы или нет доступа.
    """
    topic = await uow.topic_repository.get_active_by_id(
        topic_id,
    )
    if topic is None:
        raise EntityNotFoundError('Topic', topic_id)
    allowed = await can_read_topic(
        uow,
        topic,
        category=topic.category,
        user_uid=user_uid,
        is_admin=is_admin,
    )
    if not allowed:
        raise EntityNotFoundError('Topic', topic_id)
    return topic


async def require_topic_write(
    uow: unit_of_work.AbstractUnitOfWork,
    topic_id: int,
    *,
    user_uid: uuid.UUID,
    is_admin: bool = False,
) -> Topic:
    """
    Доступ на чтение темы плюс проверка «не закрыта».

    Args:
        uow: Unit of Work текущего запроса.
        topic_id: ID темы.
        user_uid: UID авторизованного автора.
        is_admin: True — админ может писать в закрытую.

    Returns:
        Topic, в которую можно писать.

    Raises:
        EntityNotFoundError: Нет темы или нет доступа.
        TopicClosedError: Тема закрыта (не для админа).
    """
    from forum.domain.exceptions import TopicClosedError

    topic = await require_topic_read(
        uow,
        topic_id,
        user_uid=user_uid,
        is_admin=is_admin,
    )
    if topic.is_closed and not is_admin:
        raise TopicClosedError(topic_id)
    return topic


def require_admin(is_admin: bool) -> None:
    """
    Разрешает только операции администратора форума.

    Args:
        is_admin: Флаг роли админа у текущего пользователя.

    Raises:
        PermissionDeniedError: Если вызывающий не админ.
    """
    if not is_admin:
        raise PermissionDeniedError(
            'Только администратор может управлять доступом',
        )


async def filter_visible_categories(
    uow: unit_of_work.AbstractUnitOfWork,
    categories: list[Category],
    *,
    user_uid: uuid.UUID | None,
    is_admin: bool = False,
) -> list[Category]:
    """
    Оставляет в списке только видимые категории.

    Args:
        uow: Unit of Work для ACL-проверок.
        categories: Исходный список категорий.
        user_uid: UID пользователя или None.
        is_admin: Админ видит все категории без фильтра.

    Returns:
        Подмножество categories, доступное вызывающему.
    """
    if is_admin:
        return categories
    visible: list[Category] = []
    for category in categories:
        if await can_read_category(
            uow,
            category,
            user_uid=user_uid,
            is_admin=False,
        ):
            visible.append(category)
    return visible


async def filter_visible_topics(
    uow: unit_of_work.AbstractUnitOfWork,
    topics: list[Topic],
    *,
    user_uid: uuid.UUID | None,
    is_admin: bool = False,
    category: Category | None = None,
) -> list[Topic]:
    """
    Оставляет в списке только видимые темы.

    Категории кэшируются явно: lazy `topic.category`
    в async даёт MissingGreenlet.

    Args:
        uow: Unit of Work для ACL и загрузки категорий.
        topics: Исходный список тем.
        user_uid: UID пользователя или None.
        is_admin: Админ видит все темы без фильтра.
        category: Общая родительская категория списка,
            если все темы из одной.

    Returns:
        Подмножество topics, доступное вызывающему.
    """
    if is_admin:
        return topics
    visible: list[Topic] = []
    # Не трогаем topic.category: в async это lazy-load
    # и даёт MissingGreenlet.
    category_cache: dict[int, Category | None] = {}
    if category is not None:
        category_cache[category.id] = category

    for topic in topics:
        parent = category_cache.get(topic.category_id)
        if topic.category_id not in category_cache:
            parent = (
                await uow.category_repository.get_active_by_id(
                    topic.category_id,
                )
            )
            category_cache[topic.category_id] = parent
        if await can_read_topic(
            uow,
            topic,
            category=parent,
            user_uid=user_uid,
            is_admin=False,
        ):
            visible.append(topic)
    return visible
