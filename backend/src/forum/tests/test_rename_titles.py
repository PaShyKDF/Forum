"""Тесты переименования разделов и категорий."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from forum.domain import commands
from forum.domain.exceptions import (
    CategoryTitleExistsError,
    PermissionDeniedError,
    SectionTitleExistsError,
)
from forum.service_layer.handlers.categories import (
    handle_update_category_title_command,
)
from forum.service_layer.handlers.sections import (
    handle_update_section_command,
)


def _section(
    section_id: int = 1,
    *,
    title: str = 'Раздел',
    position: int = 1,
    is_topic: bool = False,
):
    return SimpleNamespace(
        id=section_id,
        title=title,
        position=position,
        is_topic=is_topic,
    )


def _category(
    category_id: int = 10,
    *,
    title: str = 'Категория',
):
    return SimpleNamespace(
        id=category_id,
        title=title,
    )


def _section_uow(section=None):
    uow = AsyncMock()
    uow.section_repository = AsyncMock()
    uow.commit = AsyncMock()
    if section is not None:
        uow.section_repository.get_by_id = AsyncMock(
            return_value=section,
        )
        uow.section_repository.update = AsyncMock(
            side_effect=lambda entity: entity,
        )
    return uow


def _category_uow(category=None):
    uow = AsyncMock()
    uow.category_repository = AsyncMock()
    uow.commit = AsyncMock()
    if category is not None:
        uow.category_repository.get_by_id = AsyncMock(
            return_value=category,
        )
        uow.category_repository.update = AsyncMock(
            side_effect=lambda entity: entity,
        )
    return uow


@pytest.mark.asyncio
async def test_update_section_title_success():
    section = _section(title='Старое')
    uow = _section_uow(section)
    uow.section_repository.get_by_title = AsyncMock(
        return_value=None,
    )
    result = await handle_update_section_command(
        commands.UpdateSectionCommand(
            section_id=1,
            title='Новое',
            is_admin=True,
        ),
        uow,
    )
    assert result.title == 'Новое'
    assert section.title == 'Новое'
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_section_title_same_allowed():
    section = _section(title='То же')
    uow = _section_uow(section)
    uow.section_repository.get_by_title = AsyncMock(
        return_value=section,
    )
    result = await handle_update_section_command(
        commands.UpdateSectionCommand(
            section_id=1,
            title='То же',
            is_admin=True,
        ),
        uow,
    )
    assert result.title == 'То же'
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_section_title_duplicate():
    section = _section(1, title='Старое')
    other = _section(2, title='Занято')
    uow = _section_uow(section)
    uow.section_repository.get_by_title = AsyncMock(
        return_value=other,
    )
    with pytest.raises(SectionTitleExistsError):
        await handle_update_section_command(
            commands.UpdateSectionCommand(
                section_id=1,
                title='Занято',
                is_admin=True,
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_update_section_title_rejects_non_admin():
    with pytest.raises(PermissionDeniedError):
        await handle_update_section_command(
            commands.UpdateSectionCommand(
                section_id=1,
                title='Новое',
                is_admin=False,
            ),
            _section_uow(),
        )


@pytest.mark.asyncio
async def test_update_category_title_success():
    category = _category(title='Старое')
    uow = _category_uow(category)
    uow.category_repository.get_by_title = AsyncMock(
        return_value=None,
    )
    result = await handle_update_category_title_command(
        commands.UpdateCategoryTitleCommand(
            category_id=10,
            title='Новое',
            is_admin=True,
        ),
        uow,
    )
    assert result.id == 10
    assert result.title == 'Новое'
    assert category.title == 'Новое'
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_category_title_duplicate():
    category = _category(10, title='Старое')
    other = _category(11, title='Занято')
    uow = _category_uow(category)
    uow.category_repository.get_by_title = AsyncMock(
        return_value=other,
    )
    with pytest.raises(CategoryTitleExistsError):
        await handle_update_category_title_command(
            commands.UpdateCategoryTitleCommand(
                category_id=10,
                title='Занято',
                is_admin=True,
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_update_category_title_rejects_non_admin():
    with pytest.raises(PermissionDeniedError):
        await handle_update_category_title_command(
            commands.UpdateCategoryTitleCommand(
                category_id=10,
                title='Новое',
                is_admin=False,
            ),
            _category_uow(),
        )
