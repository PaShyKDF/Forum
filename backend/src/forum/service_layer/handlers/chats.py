"""Handlers личных чатов."""

from general.logger import log, logger

from forum.domain import commands
from forum.domain.exceptions import (
    ChatAccessDeniedError,
    EntityNotFoundError,
    SelfChatForbiddenError,
)
from forum.domain.schemas.chats import (
    ChatItemResponse,
    ChatMessageResponse,
    ChatMessagesPageResponse,
)
from forum.service_layer import unit_of_work
from forum.service_layer.assemblers import (
    build_chat_item,
    build_chat_message,
    build_chat_messages_page,
)
from forum.service_layer.message_body import (
    prepare_message_body,
)


def _require_body(body: str) -> str:
    """
    Нормализует и проверяет текст сообщения ЛС.

    Args:
        body: Исходный текст сообщения.

    Returns:
        Готовый к сохранению текст.

    Raises:
        DomainError: Если текст пуст или слишком длинный.
    """
    return prepare_message_body(body, max_length=10000)


@log
async def handle_get_or_create_direct_chat_command(
    command: commands.GetOrCreateDirectChatCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> ChatItemResponse:
    """
    Получает или создаёт диалог 1-на-1.

    Args:
        command: uid текущего и собеседника.
        uow: Unit of Work текущего запроса.

    Returns:
        ChatItemResponse с превью последнего сообщения.

    Raises:
        SelfChatForbiddenError: Если uid совпадают.
        EntityNotFoundError: Если собеседник не найден
            или неактивен.
    """
    if command.current_user_uid == command.other_user_uid:
        raise SelfChatForbiddenError()

    other = await uow.user_repository.get_by_id(
        command.other_user_uid,
    )
    if other is None or not other.is_active:
        raise EntityNotFoundError(
            'User',
            command.other_user_uid,
        )

    chat = await uow.chat_repository.get_or_create_direct_chat(
        command.current_user_uid,
        command.other_user_uid,
    )
    await uow.commit()

    last_map = (
        await uow.chat_message_repository
        .get_last_message_for_chat_ids([chat.id])
    )
    logger.info(
        'Диалог %s между %s и %s',
        chat.id,
        command.current_user_uid,
        command.other_user_uid,
    )
    unread_map = (
        await uow.chat_message_repository
        .count_unread_by_chat_ids(
            command.current_user_uid,
            [chat.id],
        )
    )
    return build_chat_item(
        chat,
        current_user_uid=command.current_user_uid,
        last_message=last_map.get(chat.id),
        unread_count=unread_map.get(chat.id, 0),
    )


@log
async def handle_get_my_chats_command(
    command: commands.GetMyChatsCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> list[ChatItemResponse]:
    """
    Список диалогов текущего пользователя.

    Args:
        command: uid текущего пользователя.
        uow: Unit of Work текущего запроса.

    Returns:
        Список ChatItemResponse с превью последнего
        сообщения и unread_count по каждому диалогу.
    """
    chats = await uow.chat_repository.list_user_chats(
        command.current_user_uid,
    )
    chat_ids = [chat.id for chat in chats]
    last_map = (
        await uow.chat_message_repository
        .get_last_message_for_chat_ids(chat_ids)
    )
    unread_map = (
        await uow.chat_message_repository
        .count_unread_by_chat_ids(
            command.current_user_uid,
            chat_ids,
        )
    )
    logger.info(
        'Чатов у %s: %s',
        command.current_user_uid,
        len(chats),
    )
    return [
        build_chat_item(
            chat,
            current_user_uid=command.current_user_uid,
            last_message=last_map.get(chat.id),
            unread_count=unread_map.get(chat.id, 0),
        )
        for chat in chats
    ]


@log
async def handle_get_chat_messages_command(
    command: commands.GetChatMessagesCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> ChatMessagesPageResponse:
    """
    Страница сообщений диалога для участника.

    Args:
        command: chat_id, uid, limit и before_id.
        uow: Unit of Work текущего запроса.

    Returns:
        ChatMessagesPageResponse с флагом has_more.

    Raises:
        EntityNotFoundError: Если чат не найден.
        ChatAccessDeniedError: Если пользователь не
            участник диалога.
    """
    chat = await uow.chat_repository.get_chat_for_user(
        command.chat_id,
        command.current_user_uid,
    )
    if chat is None:
        # Не раскрываем существование чужого чата
        exists = await uow.chat_repository.get_by_id(
            command.chat_id,
        )
        if exists is None:
            raise EntityNotFoundError(
                'DirectChat',
                command.chat_id,
            )
        raise ChatAccessDeniedError()

    limit = max(1, min(command.limit, 100))
    messages = await uow.chat_message_repository.list_messages(
        chat.id,
        limit=limit,
        before_id=command.before_id,
    )
    has_more = False
    if messages:
        older = await uow.chat_message_repository.list_messages(
            chat.id,
            limit=1,
            before_id=messages[0].id,
        )
        has_more = bool(older)

    return build_chat_messages_page(
        chat,
        messages,
        current_user_uid=command.current_user_uid,
        has_more=has_more,
    )


@log
async def handle_send_direct_message_command(
    command: commands.SendDirectMessageCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> ChatMessageResponse:
    """
    Отправляет текстовое сообщение в диалог.

    Args:
        command: chat_id, uid отправителя и body.
        uow: Unit of Work текущего запроса.

    Returns:
        ChatMessageResponse созданного сообщения.

    Raises:
        EntityNotFoundError: Если чат не найден.
        ChatAccessDeniedError: Если пользователь не
            участник диалога.
        DomainError: Если текст пуст или слишком длинный.
    """
    chat = await uow.chat_repository.get_chat_for_user(
        command.chat_id,
        command.current_user_uid,
    )
    if chat is None:
        exists = await uow.chat_repository.get_by_id(
            command.chat_id,
        )
        if exists is None:
            raise EntityNotFoundError(
                'DirectChat',
                command.chat_id,
            )
        raise ChatAccessDeniedError()

    body = _require_body(command.body)
    message = (
        await uow.chat_message_repository.create_message(
            chat.id,
            command.current_user_uid,
            body,
            kind='text',
        )
    )
    await uow.chat_repository.touch_updated_at(chat.id)
    await uow.commit()

    logger.info(
        'ЛС %s в чате %s от %s',
        message.id,
        chat.id,
        command.current_user_uid,
    )
    return build_chat_message(
        message,
        current_user_uid=command.current_user_uid,
    )
