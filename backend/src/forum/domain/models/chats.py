"""Модели личных чатов 1-на-1."""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forum.domain.models.base import Base
from forum.domain.models.mixins import (
    CreatedAtMixin,
    IDMixin,
    IsActiveMixin,
    UpdatedAtMixin,
)


if TYPE_CHECKING:
    from forum.domain.models.users import User


class DirectChat(
    IDMixin,
    IsActiveMixin,
    CreatedAtMixin,
    UpdatedAtMixin,
    Base,
):
    """
    Личный диалог между двумя пользователями.

    Пара участников нормализуется: user_low_id < user_high_id
    (сравнение UUID как строк), чтобы уникальность не зависела
    от порядка создания.
    """

    __table_args__ = (
        UniqueConstraint(
            'user_low_id',
            'user_high_id',
            name='uq_directchat_pair',
        ),
    )

    user_low_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('user.uid', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    user_high_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('user.uid', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    user_low: Mapped['User'] = relationship(
        foreign_keys=[user_low_id],
    )
    user_high: Mapped['User'] = relationship(
        foreign_keys=[user_high_id],
    )
    messages: Mapped[list['DirectMessage']] = relationship(
        back_populates='chat',
        cascade='all, delete-orphan',
        order_by='DirectMessage.created_at',
    )

    def has_participant(self, user_uid: uuid.UUID) -> bool:
        """
        Является ли текущий пользователь участником чата.

        Args:
            user_uid (uuid.UUID): UID текущего пользователя.

        Returns:
            bool: True если переданный пользователь участник чата.
        """
        return (
            self.user_low_id == user_uid
            or self.user_high_id == user_uid
        )

    def other_user_id(
        self,
        user_uid: uuid.UUID,
    ) -> uuid.UUID:
        """
        Возвращает идентификатор другого участника чата.

        Args:
            user_uid (uuid.UUID): UID текущего пользователя.

        Returns:
            uuid.UUID: UID второго участника.
        """
        if self.user_low_id == user_uid:
            return self.user_high_id
        return self.user_low_id

    def __str__(self) -> str:
        return (
            f'DirectChat(id={self.id}, '
            f'{self.user_low_id}↔{self.user_high_id})'
        )


class DirectMessage(
    IDMixin,
    IsActiveMixin,
    CreatedAtMixin,
    UpdatedAtMixin,
    Base,
):
    """Сообщение в личном чате."""

    chat_id: Mapped[int] = mapped_column(
        ForeignKey('directchat.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('user.uid', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    # text | image | video | gif | file (пока только text)
    kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default='text',
        server_default='text',
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # None — получатель ещё не видел сообщение
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )

    chat: Mapped['DirectChat'] = relationship(
        back_populates='messages',
        foreign_keys=[chat_id],
    )
    sender: Mapped['User'] = relationship(
        foreign_keys=[sender_id],
    )

    def __str__(self) -> str:
        return (
            f'DirectMessage(id={self.id}, '
            f'chat_id={self.chat_id})'
        )
