from general.logger import log, logger

from forum.domain import commands
from forum.domain.exceptions import (
    CategoryTitleExistsError,
    DomainError,
    EntityNotFoundError,
)
from forum.domain.models import Category, Section
from forum.domain.schemas.categories import (
    CategoryDetailResponse,
    CategoryResponse,
    CreateCategoryResponse,
    HomeResponse,
    SectionDetailResponse,
)
from forum.service_layer import unit_of_work
from forum.service_layer.access_control import (
    filter_visible_categories,
    filter_visible_topics,
    require_admin,
    require_category_read,
)
from forum.service_layer.assemblers import (
    build_category_detail,
    build_home_response,
    build_section_detail,
)
from forum.service_layer.handlers.category_summaries import (
    build_category_summaries,
)
from forum.service_layer.handlers.topic_summaries import (
    build_topic_summaries,
)
from forum.service_layer.message_body import (
    sanitize_message_body,
)
from forum.service_layer.timeutils import moscow_today_start_utc


async def _build_section_with_categories(
    uow: unit_of_work.AbstractUnitOfWork,
    section: Section,
    *,
    user_uid,
    is_admin: bool,
) -> SectionDetailResponse:
    """
    Собирает раздел со списком видимых категорий.

    Args:
        uow: Unit of Work текущего запроса.
        section: ORM Section.
        user_uid: uid зрителя или None для гостя.
        is_admin: Флаг администратора форума.

    Returns:
        SectionDetailResponse со статистикой категорий.
    """
    categories = await uow.category_repository.list_filtered(
        section_id=section.id,
    )
    categories = await filter_visible_categories(
        uow,
        categories,
        user_uid=user_uid,
        is_admin=is_admin,
    )
    summaries = await build_category_summaries(
        uow,
        categories,
        user_uid=user_uid,
        is_admin=is_admin,
    )
    if is_admin:
        for item in summaries:
            item.can_manage = True
    return build_section_detail(section, summaries)


@log
async def handle_get_home_command(
    command: commands.GetHomeCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> HomeResponse:
    """
    Собирает контент главной страницы форума.

    Включает спец. и обычные разделы с категориями,
    счётчики сообщества и активных за сегодня.

    Args:
        command: uid зрителя и флаг is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        HomeResponse для главной страницы.
    """
    special_sections = (
        await uow.section_repository.list_filtered(
            is_topic=True,
        )
    )
    regular_sections = (
        await uow.section_repository.list_filtered(
            is_topic=False,
        )
    )
    special_details = [
        await _build_section_with_categories(
            uow,
            section,
            user_uid=command.current_user_uid,
            is_admin=command.is_admin,
        )
        for section in special_sections
    ]
    regular_details = [
        await _build_section_with_categories(
            uow,
            section,
            user_uid=command.current_user_uid,
            is_admin=command.is_admin,
        )
        for section in regular_sections
    ]
    logger.info(
        'Главная: спец. разделов=%s, разделов=%s',
        len(special_details),
        len(regular_details),
    )
    community_members_count = (
        await uow.user_repository.count_active_users()
    )
    today_active_members_count = (
        await uow.user_repository.count_active_since(
            moscow_today_start_utc(),
        )
    )
    return build_home_response(
        special_details,
        regular_details,
        community_members_count=community_members_count,
        today_active_members_count=today_active_members_count,
    )


@log
async def handle_get_categories_command(
    command: commands.GetCategoriesCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> list[CategoryResponse]:
    """
    Список видимых категорий со статистикой.

    Args:
        command: Опциональный section_id, uid и
            is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        Список CategoryResponse.
    """
    categories = await uow.category_repository.list_filtered(
        section_id=command.section_id,
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
    logger.info('Найдено категорий: %s', len(summaries))
    return summaries


@log
async def handle_get_category_by_id_command(
    command: commands.GetCategoryByIdCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> CategoryDetailResponse:
    """
    Страница категории: метаданные и список тем.

    Args:
        command: category_id, uid и флаг is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        CategoryDetailResponse с TopicSummaryResponse.

    Raises:
        EntityNotFoundError: Если категория недоступна
            или не найдена.
    """
    category = await require_category_read(
        uow,
        command.category_id,
        user_uid=command.current_user_uid,
        is_admin=command.is_admin,
    )

    topics = await uow.topic_repository.list_filtered(
        category_id=category.id,
    )
    topics = await filter_visible_topics(
        uow,
        topics,
        user_uid=command.current_user_uid,
        is_admin=command.is_admin,
        category=category,
    )
    summaries = await build_topic_summaries(uow, topics)
    if command.is_admin:
        for item in summaries:
            item.can_manage = True

    logger.info(
        'Категория %s: тем=%s',
        category.id,
        len(summaries),
    )
    return build_category_detail(
        category,
        summaries,
        can_manage=command.is_admin,
    )


def _require_category_title(title: str) -> str:
    """
    Нормализует название категории.

    Args:
        title: Исходное название.

    Returns:
        Непустая строка после strip.

    Raises:
        DomainError: Если название пустое.
    """
    cleaned = title.strip()
    if not cleaned:
        raise DomainError(
            'Название категории не может быть пустым',
            'EMPTY_TITLE',
        )
    return cleaned


@log
async def handle_create_category_command(
    command: commands.CreateCategoryCommand,
    uow: unit_of_work.AbstractUnitOfWork,
) -> CreateCategoryResponse:
    """
    Создаёт категорию в разделе (только админ).

    Args:
        command: section_id, title, description,
            is_restricted, allowed_user_uids, is_admin.
        uow: Unit of Work текущего запроса.

    Returns:
        CreateCategoryResponse с id новой категории.

    Raises:
        PermissionDeniedError: Если вызывающий не админ.
        EntityNotFoundError: Если раздел не найден.
        CategoryTitleExistsError: Если название занято.
        DomainError: Если title пустой.
    """
    require_admin(command.is_admin)

    section = await uow.section_repository.get_active_by_id(
        command.section_id,
    )
    if section is None:
        raise EntityNotFoundError(
            'Section',
            command.section_id,
        )

    title = _require_category_title(command.title)
    description = None
    if command.description is not None:
        description = (
            sanitize_message_body(command.description)
            or None
        )

    existing = await uow.category_repository.get_by_title(
        title,
    )
    if existing is not None:
        raise CategoryTitleExistsError(title)

    is_restricted = bool(command.is_restricted)
    allowed_uids = list(command.allowed_user_uids or [])
    max_position = (
        await uow.category_repository.get_max_position(
            section.id,
        )
    )

    category = Category(
        section_id=section.id,
        title=title,
        description=description,
        position=max_position + 1,
        is_restricted=is_restricted,
    )
    category = await uow.category_repository.add(category)

    if is_restricted and allowed_uids:
        await uow.content_acl_repository.set_category_users(
            category.id,
            allowed_uids,
        )

    await uow.commit()

    logger.info(
        'Создана категория %s в разделе %s restricted=%s',
        category.id,
        section.id,
        is_restricted,
    )
    return CreateCategoryResponse(
        id=category.id,
        title=category.title,
        section_id=category.section_id,
    )
