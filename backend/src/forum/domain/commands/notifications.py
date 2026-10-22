"""Команды CQRS для уведомлений."""

from dataclasses import dataclass, field
import uuid

from forum.domain.commands.base import Command


@dataclass
class GetMyNotificationsCommand(Command):
    """Список непрочитанных уведомлений пользователя."""

    current_user_uid: uuid.UUID
    limit: int = 50


@dataclass
class MarkNotificationReadCommand(Command):
    """Пометить уведомление прочитанным (переход по клику)."""

    notification_id: int
    current_user_uid: uuid.UUID


@dataclass
class DismissNotificationCommand(Command):
    """Удалить одно уведомление из списка."""

    notification_id: int
    current_user_uid: uuid.UUID


@dataclass
class ClearNotificationsCommand(Command):
    """Очистить все непрочитанные уведомления."""

    current_user_uid: uuid.UUID


@dataclass
class GetUnreadChatCountCommand(Command):
    """Счётчик непрочитанных личных сообщений."""

    current_user_uid: uuid.UUID


@dataclass
class MarkChatMessagesVisibleCommand(Command):
    """Пометить видимые ЛС как прочитанные."""

    current_user_uid: uuid.UUID
    message_ids: list[int] = field(default_factory=list)
