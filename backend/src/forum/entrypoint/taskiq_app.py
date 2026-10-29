"""Точка входа Taskiq worker."""

from forum.config import taskiq_broker

# Импорт задач для регистрации в брокере
from forum.service_layer.tasks import (  # noqa: F401
    example,  # noqa: F401
    notifications,
    topic_views,
    visitors,
)


__all__ = ['taskiq_broker']
