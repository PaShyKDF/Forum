"""Периодическая очистка устаревших гостевых пользователей."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from forum.config import configuration, taskiq_broker
from forum.service_layer.timeutils import utc_now_naive
from forum.service_layer.unit_of_work import UnitOfWork
from general.logger import logger


@dataclass(frozen=True)
class GuestsCleanupResult:
    """Итог одного запуска очистки гостей."""

    deleted_count: int
    batches_count: int
    errors_count: int


async def cleanup_stale_guests_core(
    uow_factory: Callable[[], UnitOfWork] = UnitOfWork,
    *,
    retention_days: int | None = None,
    batch_size: int | None = None,
    max_batches: int | None = None,
) -> GuestsCleanupResult:
    """
    Ядро удаления устаревших гостей.

    Удаляет is_guest=True, у которых last_seen_at
    (или created_at) старше retention_days. Батчами
    до max_batches.

    Args:
        uow_factory: фабрика UnitOfWork.
        retention_days: порог дней или None из конфига.
        batch_size: размер батча или None из конфига.
        max_batches: лимит батчей или None из конфига.

    Returns:
        GuestsCleanupResult с числом удалений/батчей/ошибок.
    """
    days = (
        retention_days
        if retention_days is not None
        else configuration.visitors.cleanup_retention_days
    )
    size = (
        batch_size
        if batch_size is not None
        else configuration.visitors.cleanup_batch_size
    )
    limit_batches = (
        max_batches
        if max_batches is not None
        else configuration.visitors.cleanup_max_batches
    )
    older_than = utc_now_naive() - timedelta(days=days)

    deleted_total = 0
    batches = 0
    errors = 0
    consecutive_errors = 0

    logger.debug(
        'Запуск очистки гостей '
        '(older_than=%s, batch_size=%s, max_batches=%s)',
        older_than,
        size,
        limit_batches,
    )

    while batches < limit_batches:
        try:
            async with uow_factory() as uow:
                deleted = (
                    await uow.user_repository
                    .delete_stale_guests_batch(
                        older_than=older_than,
                        limit=size,
                    )
                )
                await uow.commit()
        except Exception:
            logger.exception(
                'Ошибка батча очистки гостей',
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
            'Удалён батч гостей: %s (всего %s)',
            deleted,
            deleted_total,
        )

    return GuestsCleanupResult(
        deleted_count=deleted_total,
        batches_count=batches,
        errors_count=errors,
    )


@taskiq_broker.task(
    schedule=[
        {
            'cron': configuration.visitors.cleanup_cron,
            'args': [],
        }
    ],
)
async def cleanup_stale_guests() -> None:
    """
    TaskIQ-задача очистки устаревших гостей.

    Cron из FORUM_VISITORS_CLEANUP_CRON (UTC). При
    disabled в конфиге сразу выходит без работы.
    """
    if not configuration.visitors.cleanup_enabled:
        logger.debug(
            'Очистка гостей отключена конфигурацией',
        )
        return

    result = await cleanup_stale_guests_core()
    logger.info(
        'Очистка гостей: удалено=%s, '
        'батчей=%s, ошибок=%s',
        result.deleted_count,
        result.batches_count,
        result.errors_count,
    )
