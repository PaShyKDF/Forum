"""
Сдвиг позиций разделов по шкалам is_topic.

Логика как у order_layer характеристик прогноза
в DHO: create / update / delete. Дополнительно —
перенос между обычными и специальными разделами.
"""

from general.logger import log

from forum.service_layer import unit_of_work


@log
async def handle_position_on_create(
    uow: unit_of_work.AbstractUnitOfWork,
    *,
    is_topic: bool,
    new_position: int,
) -> None:
    """
    Сдвигает соседей при создании раздела.

    Если слот new_position в шкале уже занят,
    все записи с position >= new_position
    получают +1.

    Args:
        uow: Unit of Work текущей транзакции.
        is_topic: шкала (спец / обычные).
        new_position: позиция нового раздела.

    Raises:
        ValueError: если new_position < 1.
    """
    if new_position < 1:
        raise ValueError(
            'Значение position должно быть >= 1',
        )

    repo = uow.section_repository
    existing = await repo.get_by_position(
        is_topic=is_topic,
        position=new_position,
    )
    if existing is not None:
        await repo.shift_positions_up(
            is_topic=is_topic,
            from_position=new_position,
        )


@log
async def handle_position_on_update(
    uow: unit_of_work.AbstractUnitOfWork,
    *,
    section_id: int,
    is_topic: bool,
    old_position: int,
    new_position: int,
) -> None:
    """
    Сдвигает соседей при смене позиции в шкале.

    new < old: позиции в [new, old) делают +1.
    new > old: позиции в (old, new] делают -1.
    Та же позиция — без изменений.

    Args:
        uow: Unit of Work текущей транзакции.
        section_id: ID перемещаемого раздела.
        is_topic: шкала (спец / обычные).
        old_position: прежняя позиция.
        new_position: новая позиция.

    Raises:
        ValueError: если new_position < 1.
    """
    if new_position < 1:
        raise ValueError(
            'Значение position должно быть >= 1',
        )

    if old_position == new_position:
        return

    repo = uow.section_repository

    if new_position < old_position:
        sections = await repo.list_from_position(
            is_topic=is_topic,
            position=new_position,
        )
        for section in sections:
            if (
                section.id != section_id
                and new_position
                <= section.position
                < old_position
            ):
                section.position += 1
                await repo.update(section)
    else:
        sections = await repo.list_from_position(
            is_topic=is_topic,
            position=old_position + 1,
        )
        for section in sections:
            if (
                section.id != section_id
                and old_position
                < section.position
                <= new_position
            ):
                section.position -= 1
                await repo.update(section)


@log
async def handle_position_on_delete(
    uow: unit_of_work.AbstractUnitOfWork,
    *,
    is_topic: bool,
    deleted_position: int,
) -> None:
    """
    Закрывает дыру после удаления раздела.

    Все записи шкалы с position > deleted_position
    получают -1.

    Args:
        uow: Unit of Work текущей транзакции.
        is_topic: шкала удалённого раздела.
        deleted_position: позиция удалённого.
    """
    await uow.section_repository.shift_positions_down(
        is_topic=is_topic,
        after_position=deleted_position,
    )


@log
async def handle_scale_transfer(
    uow: unit_of_work.AbstractUnitOfWork,
    *,
    old_is_topic: bool,
    old_position: int,
    new_is_topic: bool,
) -> int:
    """
    Переносит раздел в другую шкалу.

    В старой шкале закрывает дыру (как при удалении).
    В новой шкале возвращает последнюю позицию
    (max + 1, пустая шкала — 1).

    Args:
        uow: Unit of Work текущей транзакции.
        old_is_topic: прежняя шкала.
        old_position: прежняя позиция.
        new_is_topic: новая шкала.

    Returns:
        Позиция в конце новой шкалы.
    """
    await handle_position_on_delete(
        uow,
        is_topic=old_is_topic,
        deleted_position=old_position,
    )
    max_position = (
        await uow.section_repository.get_max_position(
            is_topic=new_is_topic,
        )
    )
    return max_position + 1
