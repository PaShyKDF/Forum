"""Планировщик Taskiq."""

from forum.config import taskiq_scheduler
from forum.service_layer.tasks import example  # noqa: F401
from forum.service_layer.tasks import (  # noqa: F401
    notifications,
)


scheduler = taskiq_scheduler
