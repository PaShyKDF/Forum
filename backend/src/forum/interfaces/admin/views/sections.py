"""Админка разделов форума со сдвигом позиций."""

from typing import Any

from fastapi import HTTPException, Request

from forum.domain.models import Section
from forum.interfaces.admin.views.base import BaseModelView
from forum.service_layer.section_positions import (
    handle_position_on_create,
    handle_position_on_delete,
    handle_position_on_update,
    handle_scale_transfer,
)
from forum.service_layer.unit_of_work import UnitOfWork


def _parse_bool(value: Any) -> bool:
    """
    Приводит значение формы sqladmin к bool.

    Args:
        value: значение чекбокса или bool.

    Returns:
        Булево значение.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in {
        '1',
        'true',
        'yes',
        'y',
        'on',
    }


class SectionAdmin(BaseModelView, model=Section):
    """Разделы форума со сдвигом позиций по шкалам."""

    column_list = [
        'id',
        'title',
        'position',
        'is_topic',
        'is_active',
        'created_at',
    ]
    form_excluded_columns = [
        'categories',
        'created_at',
        'updated_at',
    ]
    column_searchable_list = ['title']
    column_sortable_list = [
        'id',
        'title',
        'position',
        'is_topic',
        'is_active',
        'created_at',
    ]
    column_labels = {
        'id': 'ID',
        'title': 'Название',
        'position': 'Позиция',
        'is_topic': 'Спец. раздел',
        'is_active': 'Активен',
        'categories': 'Категории',
        'created_at': 'Создан',
        'updated_at': 'Обновлён',
    }
    name = 'Раздел'
    name_plural = 'Разделы'
    category = 'Форум'
    delete_warning = (
        'Будут удалены все категории раздела, '
        'темы, сообщения, доступы и просмотры.'
    )

    async def on_model_change(
        self,
        data: dict,
        model: Any,
        is_created: bool,
        request: Request,
    ) -> None:
        """
        Сдвигает позиции соседей перед сохранением.

        При создании освобождает слот (+1 хвосту).
        При смене is_topic закрывает дыру в старой
        шкале и ставит раздел в конец новой.
        При смене position внутри шкалы — сдвиг
        промежутка как у order_layer в DHO.

        Args:
            data: данные формы.
            model: экземпляр Section.
            is_created: True при создании.
            request: HTTP-запрос админки.

        Raises:
            HTTPException: при ошибке сдвига позиций.
        """
        new_position = int(data['position'])
        new_is_topic = _parse_bool(data.get('is_topic'))

        if new_position < 1:
            raise HTTPException(
                status_code=422,
                detail='Позиция должна быть >= 1',
            )

        async with UnitOfWork() as uow:
            try:
                if is_created:
                    await handle_position_on_create(
                        uow,
                        is_topic=new_is_topic,
                        new_position=new_position,
                    )
                else:
                    old_model = (
                        await uow.section_repository.get_by_id(
                            model.id,
                        )
                    )
                    if old_model is not None:
                        old_is_topic = bool(
                            old_model.is_topic,
                        )
                        old_position = int(
                            old_model.position,
                        )
                        if old_is_topic != new_is_topic:
                            transferred = (
                                await handle_scale_transfer(
                                    uow,
                                    old_is_topic=old_is_topic,
                                    old_position=old_position,
                                    new_is_topic=new_is_topic,
                                )
                            )
                            data['position'] = transferred
                        else:
                            await handle_position_on_update(
                                uow,
                                section_id=model.id,
                                is_topic=new_is_topic,
                                old_position=old_position,
                                new_position=new_position,
                            )
                await uow.commit()
            except ValueError as error:
                await uow.rollback()
                raise HTTPException(
                    status_code=422,
                    detail=str(error),
                ) from error
            except Exception as error:
                await uow.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=(
                        'Ошибка при обработке '
                        f'позиции: {error}'
                    ),
                ) from error

        return await super().on_model_change(
            data,
            model,
            is_created,
            request,
        )

    async def on_model_delete(
        self,
        model: Any,
        request: Request,
    ) -> None:
        """
        Закрывает дыру позиций перед удалением.

        Args:
            model: удаляемый Section.
            request: HTTP-запрос админки.

        Raises:
            HTTPException: при ошибке сдвига.
        """
        async with UnitOfWork() as uow:
            try:
                await handle_position_on_delete(
                    uow,
                    is_topic=bool(model.is_topic),
                    deleted_position=int(model.position),
                )
                await uow.commit()
            except Exception as error:
                await uow.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=(
                        'Ошибка при обработке '
                        f'позиции после удаления: {error}'
                    ),
                ) from error

        return await super().on_model_delete(model, request)
