"""Маппинг доменных ошибок в HTTPException."""

from fastapi import HTTPException

from forum.domain.exceptions import (
    CategoryTitleExistsError,
    ChatAccessDeniedError,
    DomainError,
    EditWindowExpiredError,
    EntityNotFoundError,
    InvalidQuoteError,
    NestedReplyForbiddenError,
    PermissionDeniedError,
    RateLimitExceededError,
    SelfChatForbiddenError,
    TopicClosedError,
    TopicTitleExistsError,
)


def raise_http_from_domain(error: DomainError) -> None:
    """
    Преобразует DomainError в HTTPException и бросает её.

    Коды: 404 not found; 403 permission/chat/окно правки;
    409 закрыта тема / дубликат / вложенный reply;
    422 self-chat / неверная цитата; 429 rate limit;
    иначе 400.

    Args:
        error: доменное исключение.

    Raises:
        HTTPException: всегда (с detail из error.message).
    """
    if isinstance(error, EntityNotFoundError):
        raise HTTPException(
            status_code=404,
            detail=error.message,
        ) from error
    if isinstance(
        error,
        (
            PermissionDeniedError,
            ChatAccessDeniedError,
        ),
    ):
        raise HTTPException(
            status_code=403,
            detail=error.message,
        ) from error
    if isinstance(error, SelfChatForbiddenError):
        raise HTTPException(
            status_code=422,
            detail=error.message,
        ) from error
    if isinstance(error, TopicClosedError):
        raise HTTPException(
            status_code=409,
            detail=error.message,
        ) from error
    if isinstance(
        error,
        (TopicTitleExistsError, CategoryTitleExistsError),
    ):
        raise HTTPException(
            status_code=409,
            detail=error.message,
        ) from error
    if isinstance(error, NestedReplyForbiddenError):
        raise HTTPException(
            status_code=409,
            detail=error.message,
        ) from error
    if isinstance(error, InvalidQuoteError):
        raise HTTPException(
            status_code=422,
            detail=error.message,
        ) from error
    if isinstance(error, EditWindowExpiredError):
        raise HTTPException(
            status_code=403,
            detail=error.message,
        ) from error
    if isinstance(error, RateLimitExceededError):
        raise HTTPException(
            status_code=429,
            detail=error.message,
        ) from error
    raise HTTPException(
        status_code=400,
        detail=error.message,
    ) from error
