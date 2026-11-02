"""Схемы разделов форума."""

from pydantic import Field

from forum.domain.schemas.base import BaseSchema


class SectionResponse(BaseSchema):
    """Раздел без вложенных категорий (главная, списки)."""

    id: int = Field(..., description='ID раздела')
    title: str = Field(..., description='Название')
    position: int = Field(..., description='Порядок сортировки')
    is_topic: bool = Field(
        ...,
        description='Специальный раздел',
    )


class SectionBriefResponse(BaseSchema):
    """Краткие данные раздела для хлебных крошек."""

    id: int = Field(..., description='ID раздела')
    title: str = Field(..., description='Название раздела')


class CreateSectionRequest(BaseSchema):
    """Тело запроса на создание раздела."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description='Название раздела',
    )
    is_topic: bool = Field(
        False,
        description='Специальный раздел',
    )


class CreateSectionResponse(BaseSchema):
    """Ответ после создания раздела."""

    id: int = Field(..., description='ID нового раздела')
    title: str = Field(..., description='Название')
    position: int = Field(..., description='Позиция')
    is_topic: bool = Field(
        ...,
        description='Специальный раздел',
    )


class UpdateSectionRequest(BaseSchema):
    """Тело запроса на обновление раздела."""

    position: int | None = Field(
        None,
        ge=1,
        description='Новая позиция в текущей шкале',
    )
    is_topic: bool | None = Field(
        None,
        description=(
            'Смена шкалы: True — спец, False — обычный. '
            'При смене раздел встаёт в конец новой шкалы'
        ),
    )
