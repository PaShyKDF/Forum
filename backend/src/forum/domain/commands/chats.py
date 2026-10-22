"""Команды CQRS для личных чатов."""

from dataclasses import dataclass
import uuid

from forum.domain.commands.base import Command


@dataclass
class GetOrCreateDirectChatCommand(Command):
    """Получить или создать диалог с пользователем."""

    current_user_uid: uuid.UUID
    other_user_uid: uuid.UUID


@dataclass
class GetMyChatsCommand(Command):
    """Список диалогов текущего пользователя."""

    current_user_uid: uuid.UUID


@dataclass
class GetChatMessagesCommand(Command):
    """Сообщения диалога (только для участника)."""

    chat_id: int
    current_user_uid: uuid.UUID
    limit: int = 50
    before_id: int | None = None


@dataclass
class SendDirectMessageCommand(Command):
    """Отправить текстовое сообщение в диалог."""

    chat_id: int
    current_user_uid: uuid.UUID
    body: str
