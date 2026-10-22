from datetime import datetime, timedelta

from general.logger import log, logger

from forum.config import configuration
from forum.domain import commands
from forum.domain.exceptions import (
    DomainError,
    EditWindowExpiredError,
    PermissionDeniedError,
    TopicTitleExistsError,
)
from forum.domain.models import Post, Topic
from forum.domain.schemas.categories import TopicSummaryResponse
from forum.domain.schemas.topics import (
    CreateTopicResponse,
    TopicDetailResponse,
    UpdateTopicTitleResponse,
)
from forum.service_layer import unit_of_work
from forum.service_layer.access_control import (
    filter_visible_topics,
    require_category_read,
    require_topic_read,
)
from forum.service_layer.assemblers import (
    build_topic_detail,
    can_edit_topic_title,
)
from forum.service_layer.handlers.posts import (
    handle_get_topic_posts_command,
)
from forum.service_layer.handlers.spam_guard import (
    check_topic_limits,
)
from forum.service_layer.handlers.topic_summaries import (
    build_topic_summaries,
)
from forum.service_layer.message_body import (
    prepare_message_body,
)


def _require_title(title: str) -> str:
    """
    Нормализует название темы.

    Args:
        title: Исходное название.

    Returns:
        Непустая строка после strip.

    Raises:
        DomainError: Если название пустое.
    """
    cleaned = title.strip()
    if not cleaned:
        raise DomainError(
            'Название темы не может быть пустым',
            'EMPTY_TITLE',
        )
    return cleaned


def _require_body(body: str) -> str:
    """
    Нормализует и проверяет текст первого сообщения.

    Args:
        body: Исходный текст сообщения.

    Returns:
        Готовый к сохранению текст.

    Raises:
        DomainError: Если текст пуст или слишком длинный.
    """
    return prepare_message_body(body, max_length=20000)


@log
async def handle_get_topics_command(
    command: commands.GetTopicsCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> list[TopicSummaryResponse]:
    """
    Список видимых тем с фильтрами и статистикой.

    filter_by=active — последнее сообщение ≤ 7 дней.
    filter_by=participated — темы с постами текущего
    пользователя.

    Args:
        command: category_id, is_topic, filter_by,
            uid и is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        Список TopicSummaryResponse.
    """
    if command.filter_by == 'active':
        topics = await uow.topic_repository.list_active_recent()
    elif command.filter_by == 'participated':
        if command.current_user_uid is None:
            topics = []
        else:
            topics = await uow.topic_repository.list_participated(
                command.current_user_uid,
            )
    else:
        topics = await uow.topic_repository.list_filtered(
            category_id=command.category_id,
            is_topic=command.is_topic,
        )
    topics = await filter_visible_topics(
        uow,
        topics,
        user_uid=command.current_user_uid,
        is_admin=command.is_admin,
    )
    summaries = await build_topic_summaries(uow, topics)
    if command.is_admin:
        for item in summaries:
            item.can_manage = True
    logger.info('Найдено тем: %s', len(summaries))
    return summaries


@log
async def handle_get_topic_by_id_command(
    command: commands.GetTopicByIdCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> TopicDetailResponse:
    """
    Страница темы: метаданные и корневые сообщения.

    Args:
        command: topic_id, page, page_size, uid и
            is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        TopicDetailResponse с пагинацией постов.

    Raises:
        EntityNotFoundError: Если тема недоступна или
            не найдена.
    """
    topic = await require_topic_read(
        uow,
        command.topic_id,
        user_uid=command.current_user_uid,
        is_admin=command.is_admin,
    )

    posts_page = await handle_get_topic_posts_command(
        commands.GetTopicPostsCommand(
            topic_id=command.topic_id,
            page=command.page,
            page_size=command.page_size,
            current_user_uid=command.current_user_uid,
            is_admin=command.is_admin,
        ),
        uow,
    )

    logger.info(
        'Тема %s: сообщений на странице=%s',
        topic.id,
        len(posts_page.items),
    )
    return build_topic_detail(
        topic,
        posts_page,
        can_manage=command.is_admin,
        current_user_uid=command.current_user_uid,
    )


@log
async def handle_update_topic_title_command(
    command: commands.UpdateTopicTitleCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> UpdateTopicTitleResponse:
    """
    Меняет название темы автором в окне редактирования.

    Args:
        command: topic_id, author_id, title и is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        UpdateTopicTitleResponse с новым title.

    Raises:
        EntityNotFoundError: Если тема недоступна или
            не найдена.
        PermissionDeniedError: Если вызывающий не автор.
        EditWindowExpiredError: Если окно редактирования
            истекло.
        TopicTitleExistsError: Если название занято в
            категории.
        DomainError: Если title пустой.
    """
    topic = await require_topic_read(
        uow,
        command.topic_id,
        user_uid=command.author_id,
        is_admin=command.is_admin,
    )

    if topic.author_id != command.author_id:
        raise PermissionDeniedError(
            'Можно менять название только своей темы',
        )

    hours = configuration.discussions.topic_edit_window_hours
    deadline = topic.created_at + timedelta(hours=hours)
    if datetime.now() > deadline:
        raise EditWindowExpiredError(hours)

    title = _require_title(command.title)
    existing = (
        await uow.topic_repository.get_by_category_and_title(
            topic.category_id,
            title,
        )
    )
    if existing is not None and existing.id != topic.id:
        raise TopicTitleExistsError(title)

    topic.title = title
    topic = await uow.topic_repository.update(topic)
    await uow.commit()

    logger.info(
        'Название темы %s изменено на «%s»',
        topic.id,
        topic.title,
    )
    return UpdateTopicTitleResponse(
        id=topic.id,
        title=topic.title,
        can_edit_title=can_edit_topic_title(
            topic,
            command.author_id,
        ),
    )


@log
async def handle_create_topic_command(
    command: commands.CreateTopicCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> CreateTopicResponse:
    """
    Создаёт тему и первое сообщение в категории.

    Args:
        command: category_id, author_id, title, body,
            description, is_restricted,
            allowed_user_uids и is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        CreateTopicResponse с id новой темы.

    Raises:
        EntityNotFoundError: Если категория недоступна
            или не найдена.
        TopicTitleExistsError: Если название занято.
        DomainError: Пустые title/body или создание
            скрытой темы не-админом.
        RateLimitExceededError: Если превышены лимиты
            создания тем.
    """
    category = await require_category_read(
        uow,
        command.category_id,
        user_uid=command.author_id,
        is_admin=command.is_admin,
    )

    is_restricted = bool(command.is_restricted)
    allowed_uids = list(command.allowed_user_uids or [])
    if is_restricted or allowed_uids:
        if not command.is_admin:
            raise DomainError(
                'Только администратор может создавать '
                'скрытые темы',
                'PERMISSION_DENIED',
            )

    await check_topic_limits(uow, command.author_id)

    title = _require_title(command.title)
    body = _require_body(command.body)
    description = None
    if command.description is not None:
        description = command.description.strip() or None

    existing = (
        await uow.topic_repository.get_by_category_and_title(
            command.category_id,
            title,
        )
    )
    if existing is not None:
        raise TopicTitleExistsError(title)

    topic = Topic(
        category_id=command.category_id,
        author_id=command.author_id,
        title=title,
        description=description,
        position=0,
        is_restricted=is_restricted,
    )
    topic = await uow.topic_repository.add(topic)

    if is_restricted and allowed_uids:
        await uow.content_acl_repository.set_topic_users(
            topic.id,
            allowed_uids,
        )

    post = Post(
        topic_id=topic.id,
        author_id=command.author_id,
        body=body,
        reply_to_post_id=None,
        quoted_post_id=None,
        is_topic_starter=True,
    )
    await uow.post_repository.add(post)
    await uow.commit()

    logger.info(
        'Создана тема %s в категории %s restricted=%s',
        topic.id,
        category.id,
        is_restricted,
    )
    return CreateTopicResponse(
        id=topic.id,
        title=topic.title,
        category_id=topic.category_id,
    )
