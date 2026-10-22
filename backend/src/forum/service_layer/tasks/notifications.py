"""Периодическая очистка неактивных уведомлений."""

from collections.abc import Callable
from dataclasses import dataclass

from general.logger import logger

from forum.config import configuration, taskiq_broker
from forum.service_layer.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class CleanupResult:
    """Итог одного запуска очистки."""

    deleted_count: int
    batches_count: int
    errors_count: int


async def cleanup_inactive_notifications_core(
    uow_factory: Callable[[], UnitOfWork] = UnitOfWork,
    *,
    batch_size: int | None = None,
    max_batches: int | None = None,
) -> CleanupResult:
    """
    Ядро удаления неактивных уведомлений.

    Удаляет батчами до max_batches. Выделено для
    удобства тестирования (можно подставить uow_factory).

    Args:
        uow_factory: фабрика UnitOfWork.
        batch_size: размер батча или None из конфига.
        max_batches: лимит батчей или None из конфига.

    Returns:
        CleanupResult с числом удалений, батчей и ошибок.
    """
    size = (
        batch_size
        if batch_size is not None
        else configuration.notifications_cleanup.batch_size
    )
    limit_batches = (
        max_batches
        if max_batches is not None
        else configuration.notifications_cleanup.max_batches
    )

    deleted_total = 0
    batches = 0
    errors = 0
    consecutive_errors = 0

    logger.debug(
        'Запуск очистки уведомлений '
        '(batch_size=%s, max_batches=%s)',
        size,
        limit_batches,
    )

    while batches < limit_batches:
        try:
            async with uow_factory() as uow:
                repo = uow.notification_repository
                deleted = await repo.delete_inactive_batch(
                    limit=size,
                )
                await uow.commit()
        except Exception:
            logger.exception(
                'Ошибка батча очистки уведомлений',
            )
            errors += 1
            consecutive_errors += 1
            # Transient-ошибки: несколько попыток подряд
            if consecutive_errors >= 3:
                break
            continue

        consecutive_errors = 0
        if deleted == 0:
            break

        deleted_total += deleted
        batches += 1
        logger.debug(
            'Удалён батч уведомлений: %s (всего %s)',
            deleted,
            deleted_total,
        )

    return CleanupResult(
        deleted_count=deleted_total,
        batches_count=batches,
        errors_count=errors,
    )


@taskiq_broker.task(
    schedule=[
        {
            # Каждый день в 03:00
            'cron': '0 3 * * *',
            'args': [],
        }
    ],
)
async def cleanup_inactive_notifications() -> None:
    """
    TaskIQ-задача периодической очистки уведомлений.

    Запускается по cron (ежедневно в 03:00). При
    disabled в конфиге сразу выходит без работы.
    """
    if not configuration.notifications_cleanup.enabled:
        logger.debug(
            'Очистка уведомлений отключена конфигурацией',
        )
        return

    result = await cleanup_inactive_notifications_core()
    logger.info(
        'Очистка уведомлений: удалено=%s, '
        'батчей=%s, ошибок=%s',
        result.deleted_count,
        result.batches_count,
        result.errors_count,
    )
