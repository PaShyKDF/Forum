"""Handlers уведомлений о ответах/цитатах и ЛС-счётчиков."""

from general.logger import log, logger

from forum.config import configuration
from forum.domain import commands
from forum.domain.exceptions import EntityNotFoundError
from forum.domain.schemas.base import SuccessResponse
from forum.domain.schemas.notifications import (
    MarkChatMessagesVisibleResponse,
    TopicNotificationItemResponse,
    TopicNotificationsListResponse,
    UnreadCountResponse,
)
from forum.service_layer import unit_of_work
from forum.service_layer.assemblers import (
    build_topic_notification_item,
)
from forum.service_layer.timeutils import utc_now_naive


async def _build_notification_item(
    uow: unit_of_work.AbstractUnitOfWork,
    notification,
) -> TopicNotificationItemResponse:
    """
    Собирает DTO уведомления с номерами страниц.

    Считает roots_page / replies_page, чтобы фронт
    мог открыть нужное сообщение в теме.

    Args:
        uow: Unit of Work текущего запроса.
        notification: ORM TopicNotification (с post
            или только post_id).

    Returns:
        TopicNotificationItemResponse для списка.
    """
    post = notification.post
    roots_page_size = configuration.discussions.roots_page_size
    replies_page_size = (
        configuration.discussions.replies_page_size
    )

    parent_post_id = None
    roots_page = 1
    replies_page = None

    if post is None:
        post = await uow.post_repository.get_active_by_id(
            notification.post_id,
        )

    if post is not None:
        if post.reply_to_post_id is None:
            newer = await uow.post_repository.count_newer_roots(
                post.topic_id,
                post.created_at,
            )
            roots_page = newer // roots_page_size + 1
        else:
            parent_post_id = post.reply_to_post_id
            parent = await uow.post_repository.get_active_by_id(
                parent_post_id,
            )
            if parent is not None:
                newer_roots = (
                    await uow.post_repository.count_newer_roots(
                        parent.topic_id,
                        parent.created_at,
                    )
                )
                roots_page = (
                    newer_roots // roots_page_size + 1
                )
            newer_replies = (
                await uow.post_repository.count_newer_replies(
                    parent_post_id,
                    post.created_at,
                )
            )
            replies_page = (
                newer_replies // replies_page_size + 1
            )

    return build_topic_notification_item(
        notification,
        parent_post_id=parent_post_id,
        roots_page=roots_page,
        replies_page=replies_page,
    )


@log
async def handle_get_my_notifications_command(
    command: commands.GetMyNotificationsCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> TopicNotificationsListResponse:
    """
    Список непрочитанных уведомлений пользователя.

    Args:
        command: uid пользователя и limit.
        uow: Unit of Work текущего запроса.

    Returns:
        TopicNotificationsListResponse с items и
        unread_count.
    """
    limit = max(1, min(command.limit, 100))
    items = await uow.notification_repository.list_active_unread(
        command.current_user_uid,
        limit=limit,
    )
    unread_count = (
        await uow.notification_repository.count_active_unread(
            command.current_user_uid,
        )
    )
    built = [
        await _build_notification_item(uow, item)
        for item in items
    ]
    logger.info(
        'Уведомлений у %s: %s',
        command.current_user_uid,
        unread_count,
    )
    return TopicNotificationsListResponse(
        items=built,
        unread_count=unread_count,
    )


@log
async def handle_mark_notification_read_command(
    command: commands.MarkNotificationReadCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> SuccessResponse:
    """
    Помечает уведомление прочитанным и скрывает его.

    Args:
        command: notification_id и uid владельца.
        uow: Unit of Work текущего запроса.

    Returns:
        SuccessResponse об успешном прочтении.

    Raises:
        EntityNotFoundError: Если уведомление не найдено
            или чужое.
    """
    notification = await uow.notification_repository.mark_read(
        command.notification_id,
        command.current_user_uid,
        read_at=utc_now_naive(),
    )
    if notification is None:
        raise EntityNotFoundError(
            'TopicNotification',
            command.notification_id,
        )
    # После перехода скрываем из списка
    notification.is_active = False
    await uow.commit()
    return SuccessResponse(
        success=True,
        message='Уведомление прочитано',
    )


@log
async def handle_dismiss_notification_command(
    command: commands.DismissNotificationCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> SuccessResponse:
    """
    Удаляет одно уведомление из списка (крестик).

    Args:
        command: notification_id и uid владельца.
        uow: Unit of Work текущего запроса.

    Returns:
        SuccessResponse об успешном удалении.

    Raises:
        EntityNotFoundError: Если уведомление не найдено
            или чужое.
    """
    ok = await uow.notification_repository.dismiss(
        command.notification_id,
        command.current_user_uid,
    )
    if not ok:
        raise EntityNotFoundError(
            'TopicNotification',
            command.notification_id,
        )
    await uow.commit()
    return SuccessResponse(
        success=True,
        message='Уведомление удалено',
    )


@log
async def handle_clear_notifications_command(
    command: commands.ClearNotificationsCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> SuccessResponse:
    """
    Очищает все непрочитанные уведомления пользователя.

    Args:
        command: uid текущего пользователя.
        uow: Unit of Work текущего запроса.

    Returns:
        SuccessResponse об успешной очистке.
    """
    cleared = await uow.notification_repository.clear_all(
        command.current_user_uid,
    )
    await uow.commit()
    logger.info(
        'Очищено уведомлений у %s: %s',
        command.current_user_uid,
        cleared,
    )
    return SuccessResponse(
        success=True,
        message='Уведомления очищены',
    )


@log
async def handle_get_unread_chat_count_command(
    command: commands.GetUnreadChatCountCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> UnreadCountResponse:
    """
    Счётчик непрочитанных личных сообщений.

    Args:
        command: uid текущего пользователя.
        uow: Unit of Work текущего запроса.

    Returns:
        UnreadCountResponse с unread_count.
    """
    count = (
        await uow.chat_message_repository.count_unread_for_user(
            command.current_user_uid,
        )
    )
    return UnreadCountResponse(unread_count=count)


@log
async def handle_mark_chat_messages_visible_command(
    command: commands.MarkChatMessagesVisibleCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> MarkChatMessagesVisibleResponse:
    """
    Помечает видимые входящие ЛС прочитанными.

    Args:
        command: uid и список message_ids (до 100).
        uow: Unit of Work текущего запроса.

    Returns:
        MarkChatMessagesVisibleResponse с marked_ids
        и актуальным unread_count.
    """
    ids = list(dict.fromkeys(command.message_ids or []))[:100]
    marked = await uow.chat_message_repository.mark_visible(
        user_uid=command.current_user_uid,
        message_ids=ids,
        read_at=utc_now_naive(),
    )
    if marked:
        await uow.commit()
    unread = (
        await uow.chat_message_repository.count_unread_for_user(
            command.current_user_uid,
        )
    )
    return MarkChatMessagesVisibleResponse(
        marked_ids=marked,
        unread_count=unread,
    )
