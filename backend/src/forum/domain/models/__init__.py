"""Доменные модели форума.

Добавляйте новые модели сюда и импортируйте их,
чтобы Alembic видел их при autogenerate.
"""

from .base import Base
from .categories import Category
from .chats import DirectChat, DirectMessage
from .content_acl import CategoryUserAccess, TopicUserAccess
from .mixins import (
    CreatedAtMixin,
    DescriptionMixin,
    IDMixin,
    IsActiveMixin,
    PositionMixin,
    TitleNonUniqueMixin,
    TitleUniqueMixin,
    UpdatedAtMixin,
)
from .notifications import TopicNotification
from .posts import Post
from .sections import Section
from .support import SupportTicket
from .topics import Topic
from .users import User


__all__ = [
    'Base',
    'Category',
    'CategoryUserAccess',
    'CreatedAtMixin',
    'DescriptionMixin',
    'DirectChat',
    'DirectMessage',
    'IDMixin',
    'IsActiveMixin',
    'PositionMixin',
    'Post',
    'Section',
    'SupportTicket',
    'TitleNonUniqueMixin',
    'TitleUniqueMixin',
    'Topic',
    'TopicNotification',
    'TopicUserAccess',
    'UpdatedAtMixin',
    'User',
]
