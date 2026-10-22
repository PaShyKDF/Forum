from forum.config import taskiq_broker
from general.logger import logger


@taskiq_broker.task(schedule=[{'cron': '0 * * * *'}])
async def heartbeat_task() -> None:
    """
    Пример периодической задачи (каждый час).

    Пишет в лог, что воркер TaskIQ активен.
    """
    logger.info('Taskiq heartbeat: воркер активен')


@taskiq_broker.task
async def example_background_task(message: str) -> str:
    """
    Пример фоновой задачи, вызываемой из кода.

    Args:
        message: произвольная строка для лога и ответа.

    Returns:
        Строка вида 'Обработано: …'.
    """
    logger.info(f'Фоновая задача: {message}')
    return f'Обработано: {message}'
