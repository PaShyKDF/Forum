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
