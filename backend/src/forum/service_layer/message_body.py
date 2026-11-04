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
    'a',
    'span',
})
ALLOWED_ATTRIBUTES = {
    # rel добавляет nh3 через link_rel; в attributes его быть не должно
    'a': {'href', 'target'},
    'span': {'class'},
}
ALLOWED_URL_SCHEMES = frozenset({'http', 'https'})
SPOILER_CLASS_VALUES = frozenset({'spoiler'})
_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')
_EMPTY_ANCHOR_RE = re.compile(
    r'<a(?![^>]*\bhref=)[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_PLAIN_SPAN_RE = re.compile(
    r'<span(?![^>]*\bclass=)[^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)


def _attribute_filter(
    tag: str,
    attr: str,
    value: str,
) -> str | None:
    """
    Фильтрует атрибуты после allowlist nh3.

    Для span оставляет только class=spoiler.
    Для a нормализует target.

    Args:
        tag: имя тега.
        attr: имя атрибута.
        value: значение атрибута.

    Returns:
        Значение атрибута или None, чтобы удалить.
    """
    if tag == 'span' and attr == 'class':
        classes = [
            part
            for part in value.split()
            if part in SPOILER_CLASS_VALUES
        ]
        if not classes:
            return None
        return 'spoiler'
    if tag == 'a' and attr == 'target':
        return '_blank'
    return value


def sanitize_message_body(raw: str) -> str:
    """
    Оставляет только разрешённые теги форматирования.

    Разрешены ссылки http(s) и span.spoiler.
    Пустой span без class=spoiler снимается nh3/filter.

    Args:
        raw: исходный текст (может содержать HTML).

    Returns:
        Очищенный HTML.
    """
    cleaned = (raw or '').strip()
    if not cleaned:
        return ''
    cleaned = nh3.clean(
        cleaned,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_attribute_filter,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel='noopener noreferrer',
        tag_attribute_values={
            'span': {'class': SPOILER_CLASS_VALUES},
        },
        set_tag_attribute_values={
            'a': {'target': '_blank'},
        },
    ).strip()
    # javascript: и прочие схемы дают <a> без href
    cleaned = _EMPTY_ANCHOR_RE.sub(r'\1', cleaned)
    # span без class=spoiler не нужен
    cleaned = _PLAIN_SPAN_RE.sub(r'\1', cleaned)
    return cleaned.strip()


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
