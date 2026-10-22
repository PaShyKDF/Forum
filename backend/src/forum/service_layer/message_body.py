"""Подготовка и санитизация текста сообщений."""

import re

import nh3

from forum.domain.exceptions import DomainError


ALLOWED_TAGS = frozenset({
    'b',
    'strong',
    'i',
    'em',
    'u',
    's',
    'strike',
    'del',
    'br',
})
_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')


def sanitize_message_body(raw: str) -> str:
    """
    Оставляет только разрешённые теги форматирования.

    Args:
        raw: исходный текст (может содержать HTML).

    Returns:
        Очищенный HTML без атрибутов и опасных тегов.
    """
    cleaned = (raw or '').strip()
    if not cleaned:
        return ''
    return nh3.clean(
        cleaned,
        tags=ALLOWED_TAGS,
        attributes={},
        link_rel=None,
    ).strip()


def strip_message_tags(raw: str) -> str:
    """
    Убирает HTML-теги для превью и сниппетов.

    Args:
        raw: текст с возможными HTML-тегами.

    Returns:
        Плоский текст без тегов (пробелы сжаты).
    """
    if not raw:
        return ''
    text = _TAG_RE.sub(' ', raw)
    return _WHITESPACE_RE.sub(' ', text).strip()


def prepare_message_body(
    raw: str,
    *,
    max_length: int | None = None,
) -> str:
    """
    Sanitize + проверка пустоты и длины.

    Args:
        raw: исходный body.
        max_length: лимит символов после sanitize.

    Returns:
        Готовый к сохранению body.

    Raises:
        DomainError: пустой текст или превышен лимит.
    """
    cleaned = sanitize_message_body(raw)
    if not strip_message_tags(cleaned):
        raise DomainError(
            'Текст сообщения не может быть пустым',
            'EMPTY_BODY',
        )
    if max_length is not None and len(cleaned) > max_length:
        raise DomainError(
            f'Текст сообщения слишком длинный '
            f'(макс. {max_length})',
            'BODY_TOO_LONG',
        )
    return cleaned
