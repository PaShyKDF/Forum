from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    LargeBinary,
    String,
    Uuid,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forum.domain.models.base import Base
from forum.domain.models.mixins import (
    CreatedAtMixin,
    IsActiveMixin,
    UpdatedAtMixin,
)


if TYPE_CHECKING:
    from forum.domain.models.content_acl import (
        CategoryUserAccess,
        TopicUserAccess,
    )
    from forum.domain.models.posts import Post
    from forum.domain.models.topics import Topic


class User(
    IsActiveMixin,
    CreatedAtMixin,
    UpdatedAtMixin,
    Base,
):
    """Пользователь форума."""

    uid: Mapped[uuid] = mapped_column(
        Uuid,
        primary_key=True,
        index=True,
    )
    username: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(
        String,
        unique=True,
        nullable=True,
        index=True,
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )
    display_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    initials: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    avatar_mime: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    avatar_blob: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        deferred=True,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    last_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    last_country: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    last_city: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    last_ip_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    # Cookie ID гостя (NULL у зарегистрированных)
    anon_id: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
    )
    is_guest: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    # Момент превращения гостя в аккаунт (Keycloak)
    registered_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    topics: Mapped[list['Topic']] = relationship(
        back_populates='author',
        cascade='all, delete-orphan',
        foreign_keys='Topic.author_id',
    )
    posts: Mapped[list['Post']] = relationship(
        back_populates='author',
        cascade='all, delete-orphan',
        foreign_keys='Post.author_id',
    )
    category_access_rows: Mapped[list['CategoryUserAccess']] = (
        relationship(
            back_populates='user',
            cascade='all, delete-orphan',
        )
    )
    topic_access_rows: Mapped[list['TopicUserAccess']] = (
        relationship(
            back_populates='user',
            cascade='all, delete-orphan',
        )
    )

    def __str__(self) -> str:
        return self.display_name
