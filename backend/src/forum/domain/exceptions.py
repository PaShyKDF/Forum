"""Доменные исключения форума."""


class DomainError(Exception):
    """
    Базовое исключение для доменных ошибок.

    Несёт человекочитаемое message и опциональный
    error_code для маппинга в HTTP.
    """

    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class MessageBusError(DomainError):
    """
    Ошибки шины сообщений (message bus).

    Базовый класс для сбоев диспетчеризации команд/событий.
    """

    pass


class InvalidMessageTypeError(MessageBusError):
    """
    Неподдерживаемый тип сообщения в шине.

    Возникает, если передан тип вне Command/Event.
    """

    def __init__(self, message_type: type):
        super().__init__(
            f'Неподдерживаемый тип сообщения: '
            f'{message_type.__name__}',
            'INVALID_MESSAGE_TYPE',
        )


class HandlerNotFoundError(MessageBusError):
    """
    Обработчик команды не найден в реестре шины.

    Обычно означает, что команда не зарегистрирована.
    """

    def __init__(self, command_type: type):
        super().__init__(
            f'Не найден обработчик для команды: '
            f'{command_type.__name__}',
            'HANDLER_NOT_FOUND',
        )


class EntityNotFoundError(DomainError):
    """
    Запрошенная сущность не найдена.

    Хранит entity_type и entity_id для ответа клиенту.
    """

    def __init__(self, entity_type: str, entity_id):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(
            f'{entity_type} с ID {entity_id} не найден',
            'ENTITY_NOT_FOUND',
        )


class PermissionDeniedError(DomainError):
    """
    Недостаточно прав для операции.

    Используется для админских и авторских проверок.
    """

    def __init__(self, message: str = 'Недостаточно прав'):
        super().__init__(message, 'PERMISSION_DENIED')


class TopicClosedError(DomainError):
    """
    Тема закрыта для новых сообщений.

    Новые ответы и цитаты в такую тему запрещены.
    """

    def __init__(self, topic_id):
        self.topic_id = topic_id
        super().__init__(
            f'Тема {topic_id} закрыта для ответов',
            'TOPIC_CLOSED',
        )


class EditWindowExpiredError(DomainError):
    """
    Истекло окно редактирования сообщения или темы.

    hours — длительность окна из конфигурации.
    """

    def __init__(self, hours: int):
        self.hours = hours
        super().__init__(
            f'Редактирование доступно только '
            f'в течение {hours} ч. после публикации',
            'EDIT_WINDOW_EXPIRED',
        )


class NestedReplyForbiddenError(DomainError):
    """
    Ответ на ответ запрещён.

    Отвечать можно только на корневое сообщение темы.
    """

    def __init__(self):
        super().__init__(
            'Нельзя отвечать на ответ. '
            'Ответ допустим только на корневое сообщение',
            'NESTED_REPLY_FORBIDDEN',
        )


class InvalidQuoteError(DomainError):
    """
    Некорректная цитата сообщения.

    Цитируемый пост отсутствует, неактивен или из другой темы.
    """

    def __init__(
        self,
        message: str = 'Некорректная цитата',
    ):
        super().__init__(message, 'INVALID_QUOTE')


class TopicTitleExistsError(DomainError):
    """
    Тема с таким названием уже есть в категории.

    title — конфликтующее название темы.
    """

    def __init__(self, title: str):
        self.title = title
        super().__init__(
            f'Тема «{title}» уже существует в этой категории',
            'TOPIC_TITLE_EXISTS',
        )


class CategoryTitleExistsError(DomainError):
    """
    Категория с таким названием уже существует.

    title — конфликтующее название категории.
    """

    def __init__(self, title: str):
        self.title = title
        super().__init__(
            f'Категория «{title}» уже существует',
            'CATEGORY_TITLE_EXISTS',
        )


class RateLimitExceededError(DomainError):
    """
    Превышен лимит создания тем или сообщений.

    message описывает, какой именно лимит сработал.
    """

    def __init__(self, message: str):
        super().__init__(message, 'RATE_LIMIT_EXCEEDED')


class ChatAccessDeniedError(DomainError):
    """
    Нет доступа к личному чату.

    Пользователь не является участником диалога.
    """

    def __init__(
        self,
        message: str = (
            'Нет доступа к этому чату'
        ),
    ):
        super().__init__(message, 'CHAT_ACCESS_DENIED')


class SelfChatForbiddenError(DomainError):
    """
    Нельзя создать чат с самим собой.

    Запрещает диалог, где оба участника — один uid.
    """

    def __init__(self):
        super().__init__(
            'Нельзя написать сообщение самому себе',
            'SELF_CHAT_FORBIDDEN',
        )


class CategoryAccessDeniedError(DomainError):
    """
    Нет доступа к категории.

    Категория ограничена или пользователь не допущен.
    """

    def __init__(
        self,
        message: str = 'Нет доступа к этой категории',
    ):
        super().__init__(message, 'CATEGORY_ACCESS_DENIED')


class TopicAccessDeniedError(DomainError):
    """
    Нет доступа к теме.

    Тема ограничена или пользователь не допущен.
    """

    def __init__(
        self,
        message: str = 'Нет доступа к этой теме',
    ):
        super().__init__(message, 'TOPIC_ACCESS_DENIED')


__all__ = [
    'DomainError',
    'MessageBusError',
    'InvalidMessageTypeError',
    'HandlerNotFoundError',
    'EntityNotFoundError',
    'PermissionDeniedError',
    'TopicClosedError',
    'EditWindowExpiredError',
    'NestedReplyForbiddenError',
    'InvalidQuoteError',
    'TopicTitleExistsError',
    'CategoryTitleExistsError',
    'RateLimitExceededError',
    'ChatAccessDeniedError',
    'SelfChatForbiddenError',
    'CategoryAccessDeniedError',
    'TopicAccessDeniedError',
]
