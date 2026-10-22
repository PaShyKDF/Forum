"""Handlers сообщений обсуждений."""

from datetime import datetime, timedelta

from general.logger import log, logger

from forum.config import configuration
from forum.domain import commands
from forum.domain.exceptions import (
    EditWindowExpiredError,
    EntityNotFoundError,
    InvalidQuoteError,
    NestedReplyForbiddenError,
    PermissionDeniedError,
)
from forum.domain.models import Post
from forum.domain.schemas.posts import (
    PaginatedPostsResponse,
    PostItemResponse,
)
from forum.service_layer import unit_of_work
from forum.service_layer.access_control import (
    require_topic_read,
    require_topic_write,
)
from forum.service_layer.assemblers import (
    build_paginated_posts,
    build_post_item,
)
from forum.service_layer.handlers.spam_guard import (
    check_message_limits,
)
from forum.service_layer.message_body import (
    prepare_message_body,
)


async def _notify_if_needed(
    uow: unit_of_work.AbstractUnitOfWork,
    *,
    actor_id,
    recipient_id,
    topic_id: int,
    post_id: int,
    source_post_id: int,
    kind: str,
    notified: set,
) -> None:
    """
    Создаёт уведомление, если получатель ещё не в set.

    Пропускает self-notify и уже уведомлённых авторов.

    Args:
        uow: Unit of Work текущего запроса.
        actor_id: Автор нового сообщения.
        recipient_id: Получатель уведомления или None.
        topic_id: ID темы.
        post_id: ID нового сообщения.
        source_post_id: ID исходного поста (родитель/
            цитата).
        kind: Тип уведомления ('reply' / 'quote').
        notified: Множество уже уведомлённых uid.
    """
    if recipient_id is None:
        return
    if recipient_id == actor_id:
        return
    if recipient_id in notified:
        return
    await uow.notification_repository.create_notification(
        recipient_id=recipient_id,
        actor_id=actor_id,
        topic_id=topic_id,
        post_id=post_id,
        source_post_id=source_post_id,
        kind=kind,
    )
    notified.add(recipient_id)


async def _create_post_notifications(
    uow: unit_of_work.AbstractUnitOfWork,
    *,
    actor_id,
    topic_id: int,
    post: Post,
    parent: Post | None = None,
) -> None:
    """
    Создаёт уведомления на ответ и/или цитату.

    Args:
        uow: Unit of Work текущего запроса.
        actor_id: Автор нового сообщения.
        topic_id: ID темы.
        post: Созданный ORM Post.
        parent: Родительский пост для reply или None.
    """
    notified: set = set()
    if parent is not None:
        await _notify_if_needed(
            uow,
            actor_id=actor_id,
            recipient_id=parent.author_id,
            topic_id=topic_id,
            post_id=post.id,
            source_post_id=parent.id,
            kind='reply',
            notified=notified,
        )
    if post.quoted_post_id is not None:
        quoted = await uow.post_repository.get_active_by_id(
            post.quoted_post_id,
        )
        if quoted is not None:
            await _notify_if_needed(
                uow,
                actor_id=actor_id,
                recipient_id=quoted.author_id,
                topic_id=topic_id,
                post_id=post.id,
                source_post_id=quoted.id,
                kind='quote',
                notified=notified,
            )


def _normalize_page(page: int) -> int:
    """
    Приводит номер страницы к значению ≥ 1.

    Args:
        page: Запрошенный номер страницы.

    Returns:
        Корректный номер страницы.
    """
    return page if page >= 1 else 1


def _roots_page_size(page_size: int | None) -> int:
    """
    Размер страницы корневых сообщений.

    Args:
        page_size: Запрошенный размер или None.

    Returns:
        Размер из конфига или max(1, page_size).
    """
    if page_size is None:
        return configuration.discussions.roots_page_size
    return max(1, page_size)


def _replies_page_size(page_size: int | None) -> int:
    """
    Размер страницы ответов.

    Args:
        page_size: Запрошенный размер или None.

    Returns:
        Размер из конфига или max(1, page_size).
    """
    if page_size is None:
        return configuration.discussions.replies_page_size
    return max(1, page_size)


def _require_body(body: str) -> str:
    """
    Нормализует и проверяет текст сообщения темы.

    Args:
        body: Исходный текст сообщения.

    Returns:
        Готовый к сохранению текст.

    Raises:
        DomainError: Если текст пуст или слишком длинный.
    """
    return prepare_message_body(body, max_length=20000)


async def _validate_quote(
    uow: unit_of_work.AbstractUnitOfWork,
    *,
    topic_id: int,
    quoted_post_id: int | None,
    reply_to_post_id: int | None,
    self_post_id: int | None = None,
) -> int | None:
    """
    Проверяет правила цитирования в теме.

    Корневой пост: цитата только другого корневого
    сообщения той же темы. Ответ: цитата только
    sibling-ответа того же родителя.

    Args:
        uow: Unit of Work текущего запроса.
        topic_id: ID темы.
        quoted_post_id: ID цитаты или None.
        reply_to_post_id: ID родителя ответа или None
            для корневого поста.
        self_post_id: ID редактируемого поста или None.

    Returns:
        ID цитаты или None, если цитаты нет.

    Raises:
        InvalidQuoteError: Если цитата нарушает правила.
    """
    if quoted_post_id is None:
        return None

    quoted = await uow.post_repository.get_active_by_id(
        quoted_post_id,
    )
    if quoted is None:
        raise InvalidQuoteError(
            f'Цитируемое сообщение {quoted_post_id} '
            f'не найдено',
        )
    if quoted.topic_id != topic_id:
        raise InvalidQuoteError(
            'Можно цитировать только сообщения этой темы',
        )
    if self_post_id is not None and quoted.id == self_post_id:
        raise InvalidQuoteError(
            'Нельзя цитировать само сообщение',
        )

    if reply_to_post_id is None:
        if quoted.reply_to_post_id is not None:
            raise InvalidQuoteError(
                'В корневом сообщении можно цитировать '
                'только другие корневые сообщения',
            )
        return quoted.id

    if quoted.reply_to_post_id != reply_to_post_id:
        raise InvalidQuoteError(
            'В ответе можно цитировать только другие '
            'ответы того же сообщения',
        )
    return quoted.id


async def _paginated_posts(
    uow: unit_of_work.AbstractUnitOfWork,
    posts: list[Post],
    *,
    page: int,
    page_size: int,
    total: int,
    current_user_uid,
) -> PaginatedPostsResponse:
    """
    Собирает страницу постов со счётчиками ответов.

    Args:
        uow: Unit of Work текущего запроса.
        posts: Сообщения текущей страницы.
        page: Номер страницы.
        page_size: Размер страницы.
        total: Общее число элементов.
        current_user_uid: uid зрителя или None.

    Returns:
        PaginatedPostsResponse.
    """
    parent_ids = [post.id for post in posts]
    replies_counts = await uow.post_repository.get_replies_counts(
        parent_ids,
    )
    return build_paginated_posts(
        posts,
        replies_counts=replies_counts,
        page=page,
        page_size=page_size,
        total=total,
        current_user_uid=current_user_uid,
    )


@log
async def handle_get_topic_posts_command(
    command: commands.GetTopicPostsCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> PaginatedPostsResponse:
    """
    Страница корневых сообщений темы.

    Args:
        command: topic_id, page, page_size, uid и
            is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        PaginatedPostsResponse корневых постов.

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

    page = _normalize_page(command.page)
    page_size = _roots_page_size(command.page_size)
    total = await uow.post_repository.count_roots(topic.id)
    offset = (page - 1) * page_size
    posts = await uow.post_repository.list_roots(
        topic.id,
        limit=page_size,
        offset=offset,
    )
    logger.info(
        'Тема %s: корней=%s page=%s',
        topic.id,
        total,
        page,
    )
    return await _paginated_posts(
        uow,
        posts,
        page=page,
        page_size=page_size,
        total=total,
        current_user_uid=command.current_user_uid,
    )


@log
async def handle_get_post_replies_command(
    command: commands.GetPostRepliesCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> PaginatedPostsResponse:
    """
    Страница прямых ответов на корневое сообщение.

    Args:
        command: post_id родителя, page, page_size,
            uid и is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        PaginatedPostsResponse ответов.

    Raises:
        EntityNotFoundError: Если пост или тема
            недоступны.
        NestedReplyForbiddenError: Если post_id — не
            корневое сообщение.
    """
    parent = await uow.post_repository.get_active_by_id(
        command.post_id,
    )
    if parent is None:
        raise EntityNotFoundError('Post', command.post_id)
    if parent.reply_to_post_id is not None:
        raise NestedReplyForbiddenError()
    await require_topic_read(
        uow,
        parent.topic_id,
        user_uid=command.current_user_uid,
        is_admin=command.is_admin,
    )

    page = _normalize_page(command.page)
    page_size = _replies_page_size(command.page_size)
    total = await uow.post_repository.count_replies(parent.id)
    offset = (page - 1) * page_size
    posts = await uow.post_repository.list_replies(
        parent.id,
        limit=page_size,
        offset=offset,
    )
    logger.info(
        'Ответы к %s: total=%s page=%s',
        parent.id,
        total,
        page,
    )
    return await _paginated_posts(
        uow,
        posts,
        page=page,
        page_size=page_size,
        total=total,
        current_user_uid=command.current_user_uid,
    )


@log
async def handle_create_topic_post_command(
    command: commands.CreateTopicPostCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> PostItemResponse:
    """
    Создаёт корневое сообщение в теме.

    Args:
        command: topic_id, author_id, body,
            quoted_post_id и is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        PostItemResponse созданного сообщения.

    Raises:
        EntityNotFoundError: Если тема недоступна или
            не найдена.
        TopicClosedError: Если тема закрыта.
        InvalidQuoteError: Если цитата недопустима.
        DomainError: Если текст пуст или слишком длинный.
        RateLimitExceededError: Если превышены лимиты
            сообщений.
    """
    topic = await require_topic_write(
        uow,
        command.topic_id,
        user_uid=command.author_id,
        is_admin=command.is_admin,
    )

    await check_message_limits(uow, command.author_id)

    body = _require_body(command.body)
    quoted_id = await _validate_quote(
        uow,
        topic_id=topic.id,
        quoted_post_id=command.quoted_post_id,
        reply_to_post_id=None,
    )
    post = Post(
        topic_id=topic.id,
        author_id=command.author_id,
        body=body,
        reply_to_post_id=None,
        quoted_post_id=quoted_id,
        is_topic_starter=False,
    )
    post = await uow.post_repository.add(post)
    await _create_post_notifications(
        uow,
        actor_id=command.author_id,
        topic_id=topic.id,
        post=post,
        parent=None,
    )
    await uow.commit()

    post = await uow.post_repository.get_active_by_id(post.id)
    logger.info(
        'Создано сообщение %s в теме %s',
        post.id,
        topic.id,
    )
    return build_post_item(
        post,
        replies_count=0,
        current_user_uid=command.author_id,
    )


@log
async def handle_create_reply_command(
    command: commands.CreateReplyCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> PostItemResponse:
    """
    Создаёт ответ на корневое сообщение.

    Args:
        command: parent_post_id, author_id, body,
            quoted_post_id и is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        PostItemResponse созданного ответа.

    Raises:
        EntityNotFoundError: Если родитель или тема
            недоступны.
        NestedReplyForbiddenError: Если родитель — не
            корневое сообщение.
        TopicClosedError: Если тема закрыта.
        InvalidQuoteError: Если цитата недопустима.
        DomainError: Если текст пуст или слишком длинный.
        RateLimitExceededError: Если превышены лимиты
            сообщений.
    """
    parent = await uow.post_repository.get_active_by_id(
        command.parent_post_id,
    )
    if parent is None:
        raise EntityNotFoundError(
            'Post',
            command.parent_post_id,
        )
    if parent.reply_to_post_id is not None:
        raise NestedReplyForbiddenError()

    topic = await require_topic_write(
        uow,
        parent.topic_id,
        user_uid=command.author_id,
        is_admin=command.is_admin,
    )

    await check_message_limits(uow, command.author_id)

    body = _require_body(command.body)
    quoted_id = await _validate_quote(
        uow,
        topic_id=topic.id,
        quoted_post_id=command.quoted_post_id,
        reply_to_post_id=parent.id,
    )
    post = Post(
        topic_id=topic.id,
        author_id=command.author_id,
        body=body,
        reply_to_post_id=parent.id,
        quoted_post_id=quoted_id,
        is_topic_starter=False,
    )
    post = await uow.post_repository.add(post)
    await _create_post_notifications(
        uow,
        actor_id=command.author_id,
        topic_id=topic.id,
        post=post,
        parent=parent,
    )
    await uow.commit()

    post = await uow.post_repository.get_active_by_id(post.id)
    logger.info(
        'Ответ %s на сообщение %s',
        post.id,
        parent.id,
    )
    return build_post_item(
        post,
        replies_count=0,
        current_user_uid=command.author_id,
    )


@log
async def handle_update_post_command(
    command: commands.UpdatePostCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> PostItemResponse:
    """
    Редактирует своё сообщение в окне редактирования.

    Args:
        command: post_id, author_id, body,
            quoted_post_id и is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        PostItemResponse обновлённого сообщения.

    Raises:
        EntityNotFoundError: Если сообщение не найдено.
        PermissionDeniedError: Если вызывающий не автор.
        EditWindowExpiredError: Если окно редактирования
            истекло.
        InvalidQuoteError: Если цитата недопустима.
        DomainError: Если текст пуст или слишком длинный.
    """
    post = await uow.post_repository.get_active_by_id(
        command.post_id,
    )
    if post is None:
        raise EntityNotFoundError('Post', command.post_id)

    if post.author_id != command.author_id:
        raise PermissionDeniedError(
            'Можно редактировать только свои сообщения',
        )

    hours = configuration.discussions.post_edit_window_hours
    deadline = post.created_at + timedelta(hours=hours)
    if datetime.now() > deadline:
        raise EditWindowExpiredError(hours)

    body = _require_body(command.body)
    quoted_id = await _validate_quote(
        uow,
        topic_id=post.topic_id,
        quoted_post_id=command.quoted_post_id,
        reply_to_post_id=post.reply_to_post_id,
        self_post_id=post.id,
    )
    post.body = body
    post.quoted_post_id = quoted_id
    post = await uow.post_repository.update(post)
    await uow.commit()

    post = await uow.post_repository.get_active_by_id(post.id)
    replies_count = await uow.post_repository.count_replies(
        post.id,
    )
    logger.info('Сообщение %s отредактировано', post.id)
    return build_post_item(
        post,
        replies_count=replies_count,
        current_user_uid=command.author_id,
    )
