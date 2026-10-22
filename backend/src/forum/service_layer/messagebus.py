"""Шина команд и доменных событий (CQRS)."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Any, Union

from fastapi import Depends

from general.logger import logger

from forum.domain import commands, events
from forum.domain.exceptions import (
    DomainError,
    HandlerNotFoundError,
    InvalidMessageTypeError,
)
from forum.service_layer import unit_of_work
from forum.service_layer.handlers import (
    get_command_handlers,
    get_event_handlers,
)
from forum.service_layer.unit_of_work import get_unit_of_work


Message = Union[commands.Command, events.Event]


class MessageBus:
    """
    Очередь сообщений: команды и события.

    Команда выполняется синхронно в рамках handle и
    возвращает результат. Ошибки event-handler'ов
    логируются и не прерывают шину.
    """

    def __init__(
        self,
        uow: unit_of_work.AbstractUnitOfWork,
        event_handlers: dict[type[events.Event], list[Callable]],
        command_handlers: dict[
            type[commands.Command],
            Callable,
        ],
    ):
        """
        Args:
            uow: Unit of Work текущего запроса.
            event_handlers: Словарь Event → список handler'ов.
            command_handlers: Словарь Command → один handler.
        """
        self.uow = uow
        self.event_handlers = event_handlers
        self.command_handlers = command_handlers

    async def handle(self, message: Message) -> Any:
        """
        Обрабатывает сообщение и цепочку новых событий.

        Результат возвращается только для первой команды
        в очереди; события результата не дают.

        Args:
            message: Команда или событие для старта очереди.

        Returns:
            Результат handler'а основной команды или None.

        Raises:
            InvalidMessageTypeError: Неизвестный тип сообщения.
            HandlerNotFoundError: Нет handler'а для команды.
            DomainError: Бизнес-ошибка из command-handler.
        """
        self.queue = deque([message])
        main_result = None
        while self.queue:
            current_message = self.queue.popleft()
            result = await self._process_single_message(
                current_message,
            )

            if main_result is None and isinstance(
                current_message,
                commands.Command,
            ):
                main_result = result

        return main_result

    async def _process_single_message(
        self,
        message: Message,
    ) -> Any:
        """
        Диспетчеризация одного сообщения из очереди.

        Args:
            message: Команда или событие.

        Returns:
            Результат команды или None для события.

        Raises:
            InvalidMessageTypeError: Тип не Command и не Event.
        """
        if isinstance(message, events.Event):
            await self.handle_event(message)
            return None
        if isinstance(message, commands.Command):
            return await self.handle_command(message)
        raise InvalidMessageTypeError(type(message))

    async def handle_event(self, event: events.Event):
        """
        Вызывает все handler'ы события (best-effort).

        Ошибка одного handler'а логируется; остальные
        и очередь продолжают работу.

        Args:
            event: Доменное событие из UoW или входа.
        """
        if type(event) not in self.event_handlers:
            return

        for handler in self.event_handlers[type(event)]:
            try:
                logger.debug(
                    f'handling event {event} with {handler}'
                )
                await handler(event, self.uow)
                new_events = await self.uow.collect_new_events()
                self.queue.extend(new_events)
            except Exception:
                logger.exception(
                    f'Exception handling event {event}'
                )
                continue

    async def handle_command(
        self,
        command: commands.Command,
    ) -> Any:
        """
        Вызывает единственный handler команды.

        После handler'а новые события из UoW попадают
        в очередь шины (даже при DomainError).

        Args:
            command: Доменная команда.

        Returns:
            Результат handler'а команды.

        Raises:
            HandlerNotFoundError: Handler не зарегистрирован.
            DomainError: Бизнес-ошибка из handler'а.
        """
        if type(command) not in self.command_handlers:
            raise HandlerNotFoundError(type(command))

        try:
            handler = self.command_handlers[type(command)]
            result = await handler(command, self.uow)
            new_events = await self.uow.collect_new_events()
            self.queue.extend(new_events)
            return result
        except DomainError:
            new_events = await self.uow.collect_new_events()
            self.queue.extend(new_events)
            raise
        except Exception:
            new_events = await self.uow.collect_new_events()
            self.queue.extend(new_events)
            raise


async def get_message_bus(
    uow=Depends(get_unit_of_work),
) -> MessageBus:
    """
    FastAPI-зависимость: MessageBus на время запроса.

    Args:
        uow: Unit of Work из get_unit_of_work.

    Yields:
        Настроенный MessageBus с handler-словарями.
    """
    message_bus = MessageBus(
        event_handlers=get_event_handlers(),
        command_handlers=get_command_handlers(),
        uow=uow,
    )
    yield message_bus
