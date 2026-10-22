"""Обработчики команд разделов."""

from general.logger import log, logger

from forum.domain import commands
from forum.domain.exceptions import EntityNotFoundError
from forum.domain.schemas.categories import SectionDetailResponse
from forum.domain.schemas.sections import SectionResponse
from forum.service_layer import unit_of_work
from forum.service_layer.access_control import (
    filter_visible_categories,
)
from forum.service_layer.assemblers import (
    build_section_detail,
    build_section_response,
)
from forum.service_layer.handlers.category_summaries import (
    build_category_summaries,
)


@log
async def handle_get_sections_command(
    command: commands.GetSectionsCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> list[SectionResponse]:
    """
    Список разделов с опциональным фильтром is_topic.

    Args:
        command: Опциональный флаг is_topic.
        uow: Unit of Work текущего запроса.

    Returns:
        Список SectionResponse.
    """
    sections = await uow.section_repository.list_filtered(
        is_topic=command.is_topic,
    )
    logger.info('Найдено разделов: %s', len(sections))
    return [
        build_section_response(section)
        for section in sections
    ]


@log
async def handle_get_section_by_id_command(
    command: commands.GetSectionByIdCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> SectionDetailResponse:
    """
    Страница раздела со списком видимых категорий.

    Args:
        command: section_id, uid и флаг is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        SectionDetailResponse с CategoryResponse.

    Raises:
        EntityNotFoundError: Если раздел не найден.
    """
    section = await uow.section_repository.get_active_by_id(
        command.section_id,
    )
    if section is None:
        raise EntityNotFoundError(
            'Section',
            command.section_id,
        )

    categories = await uow.category_repository.list_filtered(
        section_id=section.id,
    )
    categories = await filter_visible_categories(
        uow,
        categories,
        user_uid=command.current_user_uid,
        is_admin=command.is_admin,
    )
    summaries = await build_category_summaries(
        uow,
        categories,
        user_uid=command.current_user_uid,
        is_admin=command.is_admin,
    )
    if command.is_admin:
        for item in summaries:
            item.can_manage = True
    logger.info(
        'Раздел %s: категорий=%s',
        section.id,
        len(summaries),
    )
    return build_section_detail(section, summaries)
