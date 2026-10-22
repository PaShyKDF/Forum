"""Хелперы handlers: общие выборки для списков тем."""

from forum.domain.models import Topic
from forum.domain.schemas.categories import TopicSummaryResponse
from forum.service_layer import unit_of_work
from forum.service_layer.assemblers import build_topic_summary


async def build_topic_summaries(
    uow: unit_of_work.AbstractUnitOfWork,
    topics: list[Topic],
) -> list[TopicSummaryResponse]:
    """
    Собирает TopicSummaryResponse со счётчиками.

    Одним запросом тянет posts_counts и last_posts
    для всех id, затем маппит в схемы.

    Args:
        uow: Unit of Work текущего запроса.
        topics: Список ORM Topic.

    Returns:
        Список TopicSummaryResponse в том же порядке,
        что и topics.
    """
    topic_ids = [topic.id for topic in topics]
    counts = await uow.topic_repository.get_posts_counts(
        topic_ids,
    )
    last_posts = await uow.topic_repository.get_last_posts(
        topic_ids,
    )
    return [
        build_topic_summary(
            topic,
            posts_count=counts.get(topic.id, 0),
            last_post=last_posts.get(topic.id),
        )
        for topic in topics
    ]
