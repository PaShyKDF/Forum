"""Точка входа Taskiq worker."""

from forum.config import taskiq_broker


# Импорт задач для регистрации в брокере
from forum.service_layer.tasks import example  # noqa: F401
from forum.service_layer.tasks import (  # noqa: F401
    notifications,
)


__all__ = ['taskiq_broker']
