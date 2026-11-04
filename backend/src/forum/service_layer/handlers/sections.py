"""Обработчики команд разделов."""

from general.logger import log, logger

from forum.domain import commands
from forum.domain.exceptions import (
    DomainError,
    EntityNotFoundError,
    SectionTitleExistsError,
)
from forum.domain.models import Section
from forum.domain.schemas.categories import SectionDetailResponse
from forum.domain.schemas.sections import (
    CreateSectionResponse,
    SectionResponse,
)
from forum.service_layer import unit_of_work
from forum.service_layer.access_control import (
    filter_visible_categories,
    require_admin,
)
from forum.service_layer.assemblers import (
    build_section_detail,
    build_section_response,
)
from forum.service_layer.handlers.category_summaries import (
    build_category_summaries,
)
from forum.service_layer.section_positions import (
    handle_position_on_update,
    handle_scale_transfer,
)


def _require_section_title(title: str) -> str:
    """
    Проверяет и нормализует название раздела.

    Args:
        title: исходное название.

    Returns:
        Очищенное название без крайних пробелов.

    Raises:
        DomainError: если название пустое.
    """
    cleaned = title.strip()
    if not cleaned:
        raise DomainError(
            'Название раздела не может быть пустым',
            'EMPTY_TITLE',
        )
    return cleaned


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


@log
async def handle_create_section_command(
    command: commands.CreateSectionCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> CreateSectionResponse:
    """
    Создаёт раздел в конце выбранной шкалы.

    Args:
        command: title, is_topic, is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        CreateSectionResponse нового раздела.

    Raises:
        PermissionDeniedError: если вызывающий не админ.
        SectionTitleExistsError: если название занято.
        DomainError: если title пустой.
    """
    require_admin(command.is_admin)

    title = _require_section_title(command.title)
    existing = await uow.section_repository.get_by_title(
        title,
    )
    if existing is not None:
        raise SectionTitleExistsError(title)

    is_topic = bool(command.is_topic)
    max_position = (
        await uow.section_repository.get_max_position(
            is_topic=is_topic,
        )
    )
    section = Section(
        title=title,
        position=max_position + 1,
        is_topic=is_topic,
    )
    section = await uow.section_repository.add(section)
    await uow.commit()

    logger.info(
        'Создан раздел %s is_topic=%s position=%s',
        section.id,
        section.is_topic,
        section.position,
    )
    return CreateSectionResponse(
        id=section.id,
        title=section.title,
        position=section.position,
        is_topic=section.is_topic,
    )


@log
async def handle_update_section_command(
    command: commands.UpdateSectionCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> SectionResponse:
    """
    Меняет название, позицию или шкалу раздела (админ).

    Смена is_topic: дыра в старой шкале закрывается,
    раздел встаёт в конец новой. Смена position
    внутри шкалы сдвигает соседей по правилам DHO.

    Args:
        command: section_id, title, position, is_topic,
            is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        SectionResponse обновлённого раздела.

    Raises:
        PermissionDeniedError: если вызывающий не админ.
        EntityNotFoundError: если раздел не найден.
        SectionTitleExistsError: если название занято.
        DomainError: если нет полей для обновления
            или position < 1.
    """
    require_admin(command.is_admin)

    if (
        command.position is None
        and command.is_topic is None
        and command.title is None
    ):
        raise DomainError(
            'Нужно указать title, position или is_topic',
            'EMPTY_UPDATE',
        )

    section = await uow.section_repository.get_by_id(
        command.section_id,
    )
    if section is None:
        raise EntityNotFoundError(
            'Section',
            command.section_id,
        )

    if command.title is not None:
        title = _require_section_title(command.title)
        existing = await uow.section_repository.get_by_title(
            title,
        )
        if (
            existing is not None
            and existing.id != section.id
        ):
            raise SectionTitleExistsError(title)
        section.title = title

    old_is_topic = bool(section.is_topic)
    old_position = int(section.position)

    if (
        command.is_topic is not None
        and bool(command.is_topic) != old_is_topic
    ):
        new_is_topic = bool(command.is_topic)
        new_position = await handle_scale_transfer(
            uow,
            old_is_topic=old_is_topic,
            old_position=old_position,
            new_is_topic=new_is_topic,
        )
        section.is_topic = new_is_topic
        section.position = new_position
    elif command.position is not None:
        new_position = int(command.position)
        if new_position < 1:
            raise DomainError(
                'Позиция должна быть >= 1',
                'INVALID_POSITION',
            )
        await handle_position_on_update(
            uow,
            section_id=section.id,
            is_topic=old_is_topic,
            old_position=old_position,
            new_position=new_position,
        )
        section.position = new_position

    section = await uow.section_repository.update(section)
    await uow.commit()

    logger.info(
        'Обновлён раздел %s title=%s position=%s is_topic=%s',
        section.id,
        section.title,
        section.position,
        section.is_topic,
    )
    return build_section_response(section)
