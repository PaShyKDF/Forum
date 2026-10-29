"""Периодическая очистка старых записей просмотров тем."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from forum.config import configuration, taskiq_broker
from forum.service_layer.timeutils import moscow_today
from forum.service_layer.unit_of_work import UnitOfWork
from general.logger import logger


@dataclass(frozen=True)
class TopicViewsCleanupResult:
    """Итог одного запуска очистки визитов."""

    deleted_count: int
    batches_count: int
    errors_count: int


async def cleanup_old_topic_views_core(
    uow_factory: Callable[[], UnitOfWork] = UnitOfWork,
    *,
    retention_days: int | None = None,
    batch_size: int | None = None,
    max_batches: int | None = None,
) -> TopicViewsCleanupResult:
    """
    Ядро удаления визитов старше retention_days.

    retention_days — сколько календарных суток МСК
    оставлять, включая сегодня. При 1 удаляется
    вчера и раньше (view_date < сегодня). Счётчик
    Topic.views_count не трогает. Батчами до
    max_batches.

    Args:
        uow_factory: фабрика UnitOfWork.
        retention_days: сколько дней хранить
            (включая сегодня) или None из конфига.
        batch_size: размер батча или None из конфига.
        max_batches: лимит батчей или None из конфига.

    Returns:
        TopicViewsCleanupResult с числом удалений.
    """
    days = (
        retention_days
        if retention_days is not None
        else configuration.topic_views.retention_days
    )
    size = (
        batch_size
        if batch_size is not None
        else configuration.topic_views.cleanup_batch_size
    )
    limit_batches = (
        max_batches
        if max_batches is not None
        else configuration.topic_views.cleanup_max_batches
    )
    # days=1 → before=сегодня → удалить вчера и старше
    before_date = moscow_today() - timedelta(days=days - 1)

    deleted_total = 0
    batches = 0
    errors = 0
    consecutive_errors = 0

    logger.debug(
        'Запуск очистки просмотров тем '
        '(before_date=%s, batch_size=%s, max_batches=%s)',
        before_date,
        size,
        limit_batches,
    )

    while batches < limit_batches:
        try:
            async with uow_factory() as uow:
                deleted = (
                    await uow.topic_view_repository
                    .delete_older_than_batch(
                        before_date=before_date,
                        limit=size,
                    )
                )
                await uow.commit()
        except Exception:
            logger.exception(
                'Ошибка батча очистки просмотров тем',
            )
            errors += 1
            consecutive_errors += 1
            if consecutive_errors >= 3:
                break
            continue

        consecutive_errors = 0
        if deleted == 0:
            break

        deleted_total += deleted
        batches += 1
        logger.debug(
            'Удалён батч просмотров: %s (всего %s)',
            deleted,
            deleted_total,
        )

    return TopicViewsCleanupResult(
        deleted_count=deleted_total,
        batches_count=batches,
        errors_count=errors,
    )


@taskiq_broker.task(
    schedule=[
        {
            'cron': configuration.topic_views.cleanup_cron,
            'args': [],
        }
    ],
)
async def cleanup_old_topic_views() -> None:
    """
    TaskIQ-задача очистки старых просмотров тем.

    Cron из FORUM_TOPIC_VIEWS_CLEANUP_CRON (UTC). При
    disabled в конфиге сразу выходит без работы.
    """
    if not configuration.topic_views.cleanup_enabled:
        logger.debug(
            'Очистка просмотров тем отключена '
            'конфигурацией',
        )
        return

    result = await cleanup_old_topic_views_core()
    logger.info(
        'Очистка просмотров тем: удалено=%s, '
        'батчей=%s, ошибок=%s',
        result.deleted_count,
        result.batches_count,
        result.errors_count,
    )
