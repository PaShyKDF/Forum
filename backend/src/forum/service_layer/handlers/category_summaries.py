"""Хелперы handlers: общие выборки для списков категорий."""

import uuid

from forum.domain.models import Category
from forum.domain.schemas.categories import CategoryResponse
from forum.service_layer import unit_of_work
from forum.service_layer.access_control import (
    filter_visible_topics,
)
from forum.service_layer.assemblers import (
    build_category_response,
)


async def build_category_summaries(
    uow: unit_of_work.AbstractUnitOfWork,
    categories: list[Category],
    *,
    user_uid: uuid.UUID | None = None,
    is_admin: bool = False,
) -> list[CategoryResponse]:
    """
    Собирает CategoryResponse со счётчиками и last_post.

    Для не-админов скрытые темы не попадают в counts /
    last_post; для скрытых категорий счётчики считаются
    только по видимым темам.

    Args:
        uow: Unit of Work текущего запроса.
        categories: Список ORM Category.
        user_uid: uid зрителя или None для гостя.
        is_admin: Флаг администратора форума.

    Returns:
        Список CategoryResponse в порядке categories.
    """
    if not categories:
        return []

    if is_admin:
        return await _summaries_from_repo(uow, categories)

    open_categories = [
        category
        for category in categories
        if not category.is_restricted
    ]
    restricted_categories = [
        category
        for category in categories
        if category.is_restricted
    ]

    result_by_id: dict[int, CategoryResponse] = {}

    if open_categories:
        open_summaries = await _summaries_from_repo(
            uow,
            open_categories,
            exclude_restricted_topics=True,
        )
        for item in open_summaries:
            result_by_id[item.id] = item

    for category in restricted_categories:
        topics = await uow.topic_repository.list_filtered(
            category_id=category.id,
        )
        visible = await filter_visible_topics(
            uow,
            topics,
            user_uid=user_uid,
            is_admin=False,
            category=category,
        )
        summaries = await _topic_based_category_summary(
            uow,
            category,
            visible,
        )
        result_by_id[category.id] = summaries

    return [
        result_by_id[category.id]
        for category in categories
        if category.id in result_by_id
    ]


async def _summaries_from_repo(
    uow: unit_of_work.AbstractUnitOfWork,
    categories: list[Category],
    *,
    exclude_restricted_topics: bool = False,
) -> list[CategoryResponse]:
    """
    Сводки категорий через агрегаты репозитория.

    Args:
        uow: Unit of Work текущего запроса.
        categories: Список ORM Category.
        exclude_restricted_topics: Исключать скрытые
            темы из counts и last_post.

    Returns:
        Список CategoryResponse.
    """
    category_ids = [category.id for category in categories]
    topics_counts = (
        await uow.category_repository.get_topics_counts(
            category_ids,
            exclude_restricted=exclude_restricted_topics,
        )
    )
    posts_counts = (
        await uow.category_repository.get_posts_counts(
            category_ids,
            exclude_restricted=exclude_restricted_topics,
        )
    )
    last_posts = (
        await uow.category_repository.get_last_posts(
            category_ids,
            exclude_restricted=exclude_restricted_topics,
        )
    )
    return [
        build_category_response(
            category,
            topics_count=topics_counts.get(category.id, 0),
            posts_count=posts_counts.get(category.id, 0),
            last_post=last_posts.get(category.id),
        )
        for category in categories
    ]


async def _topic_based_category_summary(
    uow: unit_of_work.AbstractUnitOfWork,
    category: Category,
    topics: list,
) -> CategoryResponse:
    """
    Сводка категории по уже отфильтрованным темам.

    Args:
        uow: Unit of Work текущего запроса.
        category: ORM Category.
        topics: Видимые темы категории.

    Returns:
        CategoryResponse со счётчиками по topics.
    """
    topic_ids = [topic.id for topic in topics]
    if not topic_ids:
        return build_category_response(
            category,
            topics_count=0,
            posts_count=0,
            last_post=None,
        )
    posts_counts = await uow.topic_repository.get_posts_counts(
        topic_ids,
    )
    last_posts = await uow.topic_repository.get_last_posts(
        topic_ids,
    )
    posts_total = sum(
        posts_counts.get(topic_id, 0)
        for topic_id in topic_ids
    )
    last_post = None
    for topic in topics:
        candidate = last_posts.get(topic.id)
        if candidate is None:
            continue
        if (
            last_post is None
            or candidate.created_at > last_post.created_at
        ):
            last_post = candidate
    return build_category_response(
        category,
        topics_count=len(topics),
        posts_count=posts_total,
        last_post=last_post,
    )
