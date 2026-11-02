"""Создаёт раздел «Общий» и привязывает категории."""

import asyncio

from sqlalchemy import text

from forum.domain.models import Section
from forum.service_layer.unit_of_work import UnitOfWork


DEFAULT_SECTION_TITLE = 'Общий'


async def _bump_zero_positions(uow: UnitOfWork) -> None:
    """
    Убирает позицию 0: сдвигает шкалу на +1.

    Args:
        uow: открытый Unit of Work.
    """
    for is_topic in (False, True):
        zero = await uow.section_repository.get_by_position(
            is_topic=is_topic,
            position=0,
        )
        if zero is not None:
            await uow.section_repository.shift_positions_up(
                is_topic=is_topic,
                from_position=0,
            )


async def ensure_default_section() -> None:
    """Гарантирует раздел «Общий» и FK у категорий."""
    async with UnitOfWork() as uow:
        exists = await uow.session.execute(
            text(
                "SELECT to_regclass('public.section')"
            ),
        )
        if exists.scalar() is None:
            print('Таблица section ещё нет, пропуск')
            return

        await _bump_zero_positions(uow)

        section = await uow.section_repository.get_by_title(
            DEFAULT_SECTION_TITLE,
        )
        if section is None:
            section = Section(
                title=DEFAULT_SECTION_TITLE,
                position=1,
                is_topic=False,
                is_active=True,
            )
            await uow.section_repository.add(section)
            await uow.session.flush()

        assigned = (
            await uow.category_repository.assign_null_to_section(
                section.id,
            )
        )

        await uow.commit()
        print(
            f'Раздел «{DEFAULT_SECTION_TITLE}» id={section.id}, '
            f'привязано категорий: {assigned}',
        )


if __name__ == '__main__':
    asyncio.run(ensure_default_section())
