"""Тесты санитизации body сообщений."""

import pytest

from forum.domain.exceptions import DomainError
from forum.service_layer.message_body import (
    prepare_message_body,
    sanitize_message_body,
    strip_message_tags,
)


def test_plain_text_unchanged():
    assert sanitize_message_body('hello') == 'hello'


def test_allowed_tags_kept():
    assert sanitize_message_body('<b>жирный</b>') == (
        '<b>жирный</b>'
    )
    assert sanitize_message_body('<i>курсив</i>') == (
        '<i>курсив</i>'
    )
    assert sanitize_message_body('<u>подчёркнутый</u>') == (
        '<u>подчёркнутый</u>'
    )
    assert sanitize_message_body('<s>зачёркнутый</s>') == (
        '<s>зачёркнутый</s>'
    )
    assert sanitize_message_body(
        '<strike>old</strike>',
    ) == '<strike>old</strike>'
    assert sanitize_message_body(
        '<strong>s</strong><em>e</em>',
    ) == '<strong>s</strong><em>e</em>'


def test_script_and_attrs_removed():
    cleaned = sanitize_message_body(
        '<script>alert(1)</script><b>ok</b>',
    )
    assert '<script>' not in cleaned
    assert cleaned == '<b>ok</b>'
    cleaned = sanitize_message_body(
        '<b onclick="alert(1)">x</b>',
    )
    assert 'onclick' not in cleaned
    assert cleaned == '<b>x</b>'


def test_links_and_images_removed():
    cleaned = sanitize_message_body(
        '<a href="javascript:alert(1)">link</a>'
        '<img onerror=alert(1) src=x>',
    )
    assert '<a' not in cleaned
    assert '<img' not in cleaned
    assert 'javascript' not in cleaned


def test_nested_allowed_tags():
    assert sanitize_message_body(
        '<b><i>text</i></b>',
    ) == '<b><i>text</i></b>'


def test_strip_tags_for_snippet():
    assert strip_message_tags('<b>hi</b> there') == (
        'hi there'
    )


def test_empty_after_sanitize_raises():
    with pytest.raises(DomainError) as exc:
        prepare_message_body('<b></b>')
    assert exc.value.error_code == 'EMPTY_BODY'
    with pytest.raises(DomainError) as exc:
        prepare_message_body('<script></script>')
    assert exc.value.error_code == 'EMPTY_BODY'


def test_max_length_after_sanitize():
    with pytest.raises(DomainError) as exc:
        prepare_message_body(
            '<b>' + ('x' * 50) + '</b>',
            max_length=20,
        )
    assert exc.value.error_code == 'BODY_TOO_LONG'


def test_prepare_keeps_formatting():
    assert prepare_message_body(
        '  <b>ok</b>  ',
        max_length=20000,
    ) == '<b>ok</b>'
