from general.logger import log, logger

from forum.domain import commands, events
from forum.service_layer import unit_of_work


@log
async def handle_echo_test_command(
    command: commands.EchoTestCommand,
    uow: unit_of_work.AbstractUnitOfWork,
):
    """
    Тестовая команда: логирует message и шлёт событие.

    Args:
        command: Текстовое поле message.
        uow: Unit of Work текущего запроса.

    Returns:
        Строка об успешном выполнении команды.
    """
    logger.info(f'Обработка тестовой команды: {command.message}')
    result = f"Команда '{command.message}' выполнена успешно!"

    event = events.EchoTestProcessed(
        message=command.message,
        result=result,
    )
    await uow.save_event(event)
    return result


@log
async def handle_echo_test_processed(
    event: events.EchoTestProcessed,
    uow: unit_of_work.AbstractUnitOfWork,
):
    """
    Обработчик события EchoTestProcessed.

    Args:
        event: Исходное message и результат команды.
        uow: Unit of Work текущего запроса.
    """
    logger.info(
        f'Событие обработано: {event.message} -> {event.result}'
    )
