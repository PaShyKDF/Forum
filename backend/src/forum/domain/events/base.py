from dataclasses import dataclass


@dataclass
class Event:
    """Базовый класс событий."""

    pass


@dataclass
class EchoTestProcessed(Event):
    """Событие после обработки тестовой команды."""

    message: str
    result: str
