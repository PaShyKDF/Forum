from dataclasses import dataclass


@dataclass
class Command:
    """Базовый класс команд."""

    pass


@dataclass
class EchoTestCommand(Command):
    """Тестовая команда для проверки MessageBus."""

    message: str = 'Тест'
