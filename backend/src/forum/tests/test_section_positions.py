"""Тесты сдвига позиций разделов по шкалам is_topic."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from forum.domain import commands
from forum.domain.exceptions import (
    DomainError,
    PermissionDeniedError,
    SectionTitleExistsError,
)
from forum.service_layer.handlers.sections import (
    handle_create_section_command,
    handle_update_section_command,
)
from forum.service_layer.section_positions import (
    handle_position_on_create,
    handle_position_on_delete,
    handle_position_on_update,
    handle_scale_transfer,
)


def _section(
    section_id: int,
    position: int,
    *,
    is_topic: bool = False,
    title: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=section_id,
        position=position,
        is_topic=is_topic,
        title=title or f'Section {section_id}',
    )


def _make_uow() -> MagicMock:
    uow = MagicMock()
    uow.section_repository = MagicMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    return uow


@pytest.mark.asyncio
async def test_create_shifts_when_slot_taken():
    """
    Создание в занятый слот сдвигает хвост на +1.
    """
    uow = _make_uow()
    uow.section_repository.get_by_position = AsyncMock(
        return_value=_section(1, 2),
    )
    uow.section_repository.shift_positions_up = AsyncMock()

    await handle_position_on_create(
        uow,
        is_topic=False,
        new_position=2,
    )

    uow.section_repository.shift_positions_up.assert_awaited_once_with(
        is_topic=False,
        from_position=2,
    )


@pytest.mark.asyncio
async def test_create_free_slot_no_shift():
    """
    Свободный слот при создании не трогает соседей.
    """
    uow = _make_uow()
    uow.section_repository.get_by_position = AsyncMock(
        return_value=None,
    )
    uow.section_repository.shift_positions_up = AsyncMock()

    await handle_position_on_create(
        uow,
        is_topic=True,
        new_position=3,
    )

    uow.section_repository.shift_positions_up.assert_not_called()


@pytest.mark.asyncio
async def test_update_move_up_shifts_range():
    """
    Перенос вверх: позиции в [new, old) делают +1.
    """
    uow = _make_uow()
    neighbors = [
        _section(10, 2),
        _section(11, 3),
        _section(12, 4),
        _section(5, 5),
    ]
    uow.section_repository.list_from_position = AsyncMock(
        return_value=neighbors,
    )
    uow.section_repository.update = AsyncMock(
        side_effect=lambda entity: entity,
    )

    await handle_position_on_update(
        uow,
        section_id=5,
        is_topic=False,
        old_position=5,
        new_position=2,
    )

    assert neighbors[0].position == 3
    assert neighbors[1].position == 4
    assert neighbors[2].position == 5
    assert neighbors[3].position == 5
    assert uow.section_repository.update.await_count == 3


@pytest.mark.asyncio
async def test_update_move_down_shifts_range():
    """
    Перенос вниз: позиции в (old, new] делают -1.
    """
    uow = _make_uow()
    neighbors = [
        _section(11, 3),
        _section(12, 4),
        _section(13, 5),
        _section(2, 2),
    ]
    uow.section_repository.list_from_position = AsyncMock(
        return_value=neighbors,
    )
    uow.section_repository.update = AsyncMock(
        side_effect=lambda entity: entity,
    )

    await handle_position_on_update(
        uow,
        section_id=2,
        is_topic=False,
        old_position=2,
        new_position=5,
    )

    assert neighbors[0].position == 2
    assert neighbors[1].position == 3
    assert neighbors[2].position == 4
    assert neighbors[3].position == 2
    assert uow.section_repository.update.await_count == 3


@pytest.mark.asyncio
async def test_update_same_position_noop():
    """
    Та же позиция не вызывает сдвиг.
    """
    uow = _make_uow()
    uow.section_repository.list_from_position = AsyncMock()

    await handle_position_on_update(
        uow,
        section_id=1,
        is_topic=False,
        old_position=3,
        new_position=3,
    )

    uow.section_repository.list_from_position.assert_not_called()


@pytest.mark.asyncio
async def test_delete_closes_gap():
    """
    Удаление сдвигает хвост шкалы на -1.
    """
    uow = _make_uow()
    uow.section_repository.shift_positions_down = AsyncMock()

    await handle_position_on_delete(
        uow,
        is_topic=True,
        deleted_position=4,
    )

    uow.section_repository.shift_positions_down.assert_awaited_once_with(
        is_topic=True,
        after_position=4,
    )


@pytest.mark.asyncio
async def test_scale_transfer_closes_gap_and_appends():
    """
    Перенос шкалы: дыра в старой, конец в новой.
    """
    uow = _make_uow()
    uow.section_repository.shift_positions_down = AsyncMock()
    uow.section_repository.get_max_position = AsyncMock(
        return_value=1,
    )

    new_position = await handle_scale_transfer(
        uow,
        old_is_topic=False,
        old_position=4,
        new_is_topic=True,
    )

    assert new_position == 2
    uow.section_repository.shift_positions_down.assert_awaited_once_with(
        is_topic=False,
        after_position=4,
    )
    uow.section_repository.get_max_position.assert_awaited_once_with(
        is_topic=True,
    )


@pytest.mark.asyncio
async def test_scale_transfer_empty_target_starts_at_one():
    """
    Перенос в пустую шкалу даёт позицию 1.
    """
    uow = _make_uow()
    uow.section_repository.shift_positions_down = AsyncMock()
    uow.section_repository.get_max_position = AsyncMock(
        return_value=0,
    )

    new_position = await handle_scale_transfer(
        uow,
        old_is_topic=True,
        old_position=1,
        new_is_topic=False,
    )

    assert new_position == 1


@pytest.mark.asyncio
async def test_create_section_appends_to_scale():
    """
    API создания ставит раздел в конец шкалы.
    """
    uow = _make_uow()
    uow.section_repository.get_by_title = AsyncMock(
        return_value=None,
    )
    uow.section_repository.get_max_position = AsyncMock(
        return_value=2,
    )

    async def add_section(entity):
        entity.id = 9
        return entity

    uow.section_repository.add = AsyncMock(
        side_effect=add_section,
    )

    result = await handle_create_section_command(
        commands.CreateSectionCommand(
            title='Новый',
            is_topic=False,
            is_admin=True,
        ),
        uow,
    )

    assert result.id == 9
    assert result.position == 3
    assert result.is_topic is False
    added = uow.section_repository.add.await_args.args[0]
    assert added.position == 3
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_section_admin_only():
    uow = _make_uow()
    with pytest.raises(PermissionDeniedError):
        await handle_create_section_command(
            commands.CreateSectionCommand(
                title='X',
                is_admin=False,
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_create_section_title_exists():
    uow = _make_uow()
    uow.section_repository.get_by_title = AsyncMock(
        return_value=_section(1, 0, title='Занят'),
    )
    with pytest.raises(SectionTitleExistsError):
        await handle_create_section_command(
            commands.CreateSectionCommand(
                title='Занят',
                is_admin=True,
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_update_section_position_shifts_neighbors():
    """
    PATCH position вызывает сдвиг внутри шкалы.
    """
    uow = _make_uow()
    section = _section(5, 4, is_topic=False)
    uow.section_repository.get_by_id = AsyncMock(
        return_value=section,
    )
    uow.section_repository.list_from_position = AsyncMock(
        return_value=[
            _section(2, 2),
            _section(3, 3),
            section,
        ],
    )
    uow.section_repository.update = AsyncMock(
        side_effect=lambda entity: entity,
    )

    result = await handle_update_section_command(
        commands.UpdateSectionCommand(
            section_id=5,
            position=2,
            is_admin=True,
        ),
        uow,
    )

    assert result.position == 2
    assert section.position == 2
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_section_transfer_scale():
    """
    PATCH is_topic переносит в конец новой шкалы.
    """
    uow = _make_uow()
    section = _section(5, 4, is_topic=False)
    uow.section_repository.get_by_id = AsyncMock(
        return_value=section,
    )
    uow.section_repository.shift_positions_down = AsyncMock()
    uow.section_repository.get_max_position = AsyncMock(
        return_value=0,
    )
    uow.section_repository.update = AsyncMock(
        side_effect=lambda entity: entity,
    )

    result = await handle_update_section_command(
        commands.UpdateSectionCommand(
            section_id=5,
            is_topic=True,
            position=99,
            is_admin=True,
        ),
        uow,
    )

    assert result.is_topic is True
    assert result.position == 1
    uow.section_repository.shift_positions_down.assert_awaited_once_with(
        is_topic=False,
        after_position=4,
    )
    uow.section_repository.get_max_position.assert_awaited_once_with(
        is_topic=True,
    )


@pytest.mark.asyncio
async def test_update_section_requires_fields():
    uow = _make_uow()
    with pytest.raises(DomainError) as exc_info:
        await handle_update_section_command(
            commands.UpdateSectionCommand(
                section_id=1,
                is_admin=True,
            ),
            uow,
        )
    assert exc_info.value.error_code == 'EMPTY_UPDATE'


@pytest.mark.asyncio
async def test_create_rejects_zero_position():
    uow = _make_uow()
    with pytest.raises(ValueError):
        await handle_position_on_create(
            uow,
            is_topic=False,
            new_position=0,
        )
