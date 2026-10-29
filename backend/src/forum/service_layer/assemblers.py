"""Сборка response-схем из ORM-моделей."""

from datetime import datetime, timedelta
import math
import uuid

from forum.config import configuration
from forum.service_layer.message_body import strip_message_tags
from forum.domain.models import (
    Category,
    DirectChat,
    DirectMessage,
    Post,
    Section,
    Topic,
    TopicNotification,
    User,
)
from forum.domain.schemas.categories import (
    AuthorResponse,
    CategoryDetailResponse,
    CategoryResponse,
    HomeResponse,
    LastPostResponse,
    SectionDetailResponse,
    TopicSummaryResponse,
)
from forum.domain.schemas.chats import (
    ChatItemResponse,
    ChatLastMessageResponse,
    ChatMessageResponse,
    ChatMessagesPageResponse,
    ChatPeerResponse,
)
from forum.domain.schemas.notifications import (
    TopicNotificationItemResponse,
)
from forum.domain.schemas.posts import (
    PaginatedPostsResponse,
    PostItemResponse,
    QuotedPostResponse,
)
from forum.domain.schemas.sections import (
    SectionBriefResponse,
    SectionResponse,
)
from forum.domain.schemas.topics import (
    CategoryBriefResponse,
    PostResponse,
    TopicDetailResponse,
)
from forum.domain.schemas.users import (
    PublicUserProfileResponse,
    UserProfileResponse,
    UserResponse,
)


def _category_core_fields(category: Category) -> dict:
    """Общие поля категории для response-схем."""
    return {
        'id': category.id,
        'title': category.title,
        'description': category.description,
        'position': category.position,
        'section_id': category.section_id,
    }


def build_last_post(
    topic: Topic,
    post: Post | None,
) -> LastPostResponse | None:
    """
    Краткое представление последнего сообщения темы.

    Args:
        topic: тема (для title в карточке).
        post: последнее сообщение или None.

    Returns:
        LastPostResponse или None, если поста/автора нет.
    """
    if post is None or post.author is None:
        return None
    return LastPostResponse(
        title=topic.title,
        author=post.author.display_name,
        author_uid=post.author.uid,
        created_at=post.created_at,
        topic_id=topic.id,
    )


def build_topic_summary(
    topic: Topic,
    *,
    posts_count: int = 0,
    last_post: Post | None = None,
) -> TopicSummaryResponse:
    """
    Строка темы для списков.

    Args:
        topic: ORM Topic.
        posts_count: число сообщений.
        last_post: последнее сообщение (опционально).

    Returns:
        TopicSummaryResponse.
    """
    return TopicSummaryResponse(
        id=topic.id,
        title=topic.title,
        description=topic.description,
        category_id=topic.category_id,
        position=topic.position,
        is_topic=topic.is_topic,
        is_pinned=topic.is_pinned,
        is_restricted=bool(
            getattr(topic, 'is_restricted', False),
        ),
        can_manage=False,
        posts_count=posts_count,
        views_count=topic.views_count,
        last_post=build_last_post(topic, last_post),
    )


def build_section_response(
    section: Section,
) -> SectionResponse:
    """
    Краткая карточка раздела.

    Args:
        section: ORM Section.

    Returns:
        SectionResponse.
    """
    return SectionResponse(
        id=section.id,
        title=section.title,
        position=section.position,
        is_topic=section.is_topic,
    )


def build_section_detail(
    section: Section,
    categories: list[CategoryResponse],
) -> SectionDetailResponse:
    """
    Страница раздела со списком категорий.

    Args:
        section: ORM Section.
        categories: уже собранные CategoryResponse.

    Returns:
        SectionDetailResponse.
    """
    return SectionDetailResponse(
        id=section.id,
        title=section.title,
        position=section.position,
        is_topic=section.is_topic,
        categories=categories,
    )


def build_home_response(
    special_sections: list[SectionDetailResponse],
    sections: list[SectionDetailResponse],
    *,
    community_members_count: int = 0,
    today_active_members_count: int = 0,
) -> HomeResponse:
    """
    Главная: спец. и обычные разделы с категориями.

    Args:
        special_sections: разделы is_topic=True с категориями.
        sections: обычные разделы с категориями.
        community_members_count: всего участников.
        today_active_members_count: активных за сегодня.

    Returns:
        HomeResponse.
    """
    return HomeResponse(
        special_sections=special_sections,
        sections=sections,
        community_members_count=community_members_count,
        today_active_members_count=today_active_members_count,
    )


def build_category_response(
    category: Category,
    *,
    topics_count: int = 0,
    posts_count: int = 0,
    last_post: Post | None = None,
) -> CategoryResponse:
    """
    Карточка категории со счётчиками и last_post.

    Args:
        category: ORM Category.
        topics_count: число активных тем.
        posts_count: число активных сообщений.
        last_post: последнее сообщение (с topic и author).

    Returns:
        CategoryResponse.
    """
    last_post_response = None
    if (
        last_post is not None
        and last_post.topic is not None
    ):
        last_post_response = build_last_post(
            last_post.topic,
            last_post,
        )
    return CategoryResponse(
        **_category_core_fields(category),
        is_restricted=bool(
            getattr(category, 'is_restricted', False),
        ),
        can_manage=False,
        topics_count=topics_count,
        posts_count=posts_count,
        last_post=last_post_response,
    )


def build_category_detail(
    category: Category,
    topics: list[TopicSummaryResponse],
    *,
    can_manage: bool = False,
) -> CategoryDetailResponse:
    """
    Страница категории со списком тем.

    Args:
        category: ORM Category.
        topics: TopicSummaryResponse по position.
        can_manage: админские кнопки в UI.

    Returns:
        CategoryDetailResponse.
    """
    section = None
    if category.section is not None:
        section = SectionBriefResponse(
            id=category.section.id,
            title=category.section.title,
        )
    return CategoryDetailResponse(
        id=category.id,
        title=category.title,
        description=category.description,
        position=category.position,
        is_restricted=bool(
            getattr(category, 'is_restricted', False),
        ),
        can_manage=can_manage,
        section=section,
        topics=topics,
    )


def _avatar_endpoint(uid: uuid.UUID) -> str:
    return f'/api/users/{uid}/avatar'


def _user_has_avatar(user: User) -> bool:
    return user.avatar_mime is not None


def _resolve_avatar_url(user: User) -> str | None:
    if _user_has_avatar(user):
        return _avatar_endpoint(user.uid)
    return user.avatar_url


def build_user_response(
    user: User,
    *,
    is_admin: bool = False,
) -> UserResponse:
    """
    Публичный профиль пользователя для API.

    Args:
        user: ORM User.
        is_admin: роль администратора форума.

    Returns:
        UserResponse.
    """
    return UserResponse(
        uid=user.uid,
        username=user.username,
        email=user.email,
        email_verified=user.email_verified,
        display_name=user.display_name,
        initials=user.initials,
        avatar_url=_resolve_avatar_url(user),
        has_avatar=_user_has_avatar(user),
        is_admin=is_admin,
    )


def build_user_profile_response(
    user: User,
    posts_count: int,
) -> UserProfileResponse:
    """
    Профиль пользователя со статистикой сообщений.

    Args:
        user: ORM User.
        posts_count: число активных сообщений.

    Returns:
        UserProfileResponse.
    """
    return UserProfileResponse(
        uid=user.uid,
        username=user.username,
        email=user.email,
        email_verified=user.email_verified,
        display_name=user.display_name,
        initials=user.initials,
        avatar_url=_resolve_avatar_url(user),
        has_avatar=_user_has_avatar(user),
        posts_count=posts_count,
    )


def build_public_user_profile_response(
    user: User,
    *,
    posts_count: int,
    topics_count: int,
) -> PublicUserProfileResponse:
    """
    Публичный профиль со статистикой.

    Args:
        user: ORM User.
        posts_count: число активных сообщений.
        topics_count: число активных тем автора.

    Returns:
        PublicUserProfileResponse.
    """
    return PublicUserProfileResponse(
        uid=user.uid,
        username=user.username,
        display_name=user.display_name,
        initials=user.initials,
        avatar_url=_resolve_avatar_url(user),
        has_avatar=_user_has_avatar(user),
        is_active=user.is_active,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        posts_count=posts_count,
        topics_count=topics_count,
    )


def build_author(author: User) -> AuthorResponse:
    """
    Автор сообщения/темы для вложенных схем.

    Args:
        author: ORM User.

    Returns:
        AuthorResponse.
    """
    return AuthorResponse(
        uid=author.uid,
        display_name=author.display_name,
        initials=author.initials,
        avatar_url=_resolve_avatar_url(author),
    )


def can_edit_post(
    post: Post,
    current_user_uid: uuid.UUID | None,
    *,
    now: datetime | None = None,
) -> bool:
    """
    Может ли пользователь редактировать пост сейчас.

    Args:
        post: ORM Post (нужны author_id, created_at).
        current_user_uid: uid текущего пользователя или None.
        now: момент проверки; по умолчанию datetime.now().

    Returns:
        True, если автор и окно редактирования не истекло.
    """
    if current_user_uid is None:
        return False
    if post.author_id != current_user_uid:
        return False
    hours = configuration.discussions.post_edit_window_hours
    deadline = post.created_at + timedelta(hours=hours)
    return (now or datetime.now()) <= deadline


def can_edit_topic_title(
    topic: Topic,
    current_user_uid: uuid.UUID | None,
    *,
    now: datetime | None = None,
) -> bool:
    """
    Может ли автор менять название темы сейчас.

    Args:
        topic: ORM Topic (нужны author_id, created_at).
        current_user_uid: uid текущего пользователя или None.
        now: момент проверки; по умолчанию datetime.now().

    Returns:
        True, если автор и окно правки названия активно.
    """
    if current_user_uid is None:
        return False
    if topic.author_id != current_user_uid:
        return False
    hours = configuration.discussions.topic_edit_window_hours
    deadline = topic.created_at + timedelta(hours=hours)
    return (now or datetime.now()) <= deadline


def build_quoted_post(
    quoted: Post | None,
) -> QuotedPostResponse | None:
    """
    Краткое представление цитаты для UI.

    Args:
        quoted: цитируемый ORM Post или None.

    Returns:
        QuotedPostResponse или None, если поста нет/неактивен.
    """
    if quoted is None or not quoted.is_active:
        return None
    snippet = strip_message_tags(quoted.body)
    if len(snippet) > 140:
        snippet = f'{snippet[:137]}...'
    author_name = (
        quoted.author.display_name
        if quoted.author is not None
        else '—'
    )
    author_uid = (
        quoted.author.uid
        if quoted.author is not None
        else None
    )
    return QuotedPostResponse(
        id=quoted.id,
        body_snippet=snippet,
        author_display_name=author_name,
        author_uid=author_uid,
        jump_target=f'#post-{quoted.id}',
    )


def build_post_item(
    post: Post,
    *,
    replies_count: int = 0,
    current_user_uid: uuid.UUID | None = None,
) -> PostItemResponse:
    """
    Одно сообщение для списков корней/ответов.

    Args:
        post: ORM Post с загруженным author.
        replies_count: число прямых ответов.
        current_user_uid: uid текущего пользователя.

    Returns:
        PostItemResponse.
    """
    return PostItemResponse(
        id=post.id,
        body=post.body,
        created_at=post.created_at,
        updated_at=post.updated_at,
        is_topic_starter=post.is_topic_starter,
        reply_to_post_id=post.reply_to_post_id,
        quoted_post=build_quoted_post(
            getattr(post, 'quoted_post', None),
        ),
        replies_count=replies_count,
        can_edit=can_edit_post(post, current_user_uid),
        author=build_author(post.author),
    )


def build_paginated_posts(
    posts: list[Post],
    *,
    replies_counts: dict[int, int],
    page: int,
    page_size: int,
    total: int,
    current_user_uid: uuid.UUID | None = None,
) -> PaginatedPostsResponse:
    """
    Страница сообщений с метаданными пагинации.

    Args:
        posts: ORM Post текущей страницы (с author).
        replies_counts: post_id → число прямых ответов.
        page: номер страницы (1-based).
        page_size: размер страницы.
        total: всего сообщений без пагинации.
        current_user_uid: uid текущего пользователя.

    Returns:
        PaginatedPostsResponse.
    """
    total_pages = (
        math.ceil(total / page_size) if page_size else 0
    )
    return PaginatedPostsResponse(
        items=[
            build_post_item(
                post,
                replies_count=replies_counts.get(post.id, 0),
                current_user_uid=current_user_uid,
            )
            for post in posts
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


def build_post_response(
    post: Post,
    *,
    replies_count: int = 0,
    current_user_uid: uuid.UUID | None = None,
) -> PostResponse:
    """
    Одно сообщение темы.

    Args:
        post: ORM Post с загруженным author.
        replies_count: число прямых ответов.
        current_user_uid: uid текущего пользователя.

    Returns:
        PostResponse.
    """
    return PostResponse(
        id=post.id,
        body=post.body,
        created_at=post.created_at,
        updated_at=post.updated_at,
        is_topic_starter=post.is_topic_starter,
        reply_to_post_id=post.reply_to_post_id,
        replies_count=replies_count,
        can_edit=can_edit_post(post, current_user_uid),
        author=build_author(post.author),
    )


def build_topic_detail(
    topic: Topic,
    posts_page: PaginatedPostsResponse,
    *,
    can_manage: bool = False,
    current_user_uid: uuid.UUID | None = None,
) -> TopicDetailResponse:
    """
    Страница темы: метаданные + страница корневых сообщений.

    Args:
        topic: ORM Topic с загруженной category.
        posts_page: пагинированные корневые сообщения.
        can_manage: админские кнопки в UI.
        current_user_uid: uid текущего пользователя.

    Returns:
        TopicDetailResponse.
    """
    section = None
    category = topic.category
    if (
        category is not None
        and getattr(category, 'section', None) is not None
    ):
        section = SectionBriefResponse(
            id=category.section.id,
            title=category.section.title,
        )
    return TopicDetailResponse(
        id=topic.id,
        title=topic.title,
        description=topic.description,
        is_pinned=topic.is_pinned,
        is_closed=topic.is_closed,
        is_restricted=bool(
            getattr(topic, 'is_restricted', False),
        ),
        can_manage=can_manage,
        can_edit_title=can_edit_topic_title(
            topic,
            current_user_uid,
        ),
        views_count=topic.views_count,
        section=section,
        category=CategoryBriefResponse(
            id=topic.category.id,
            title=topic.category.title,
        ),
        posts=posts_page,
        post_edit_window_hours=(
            configuration.discussions.post_edit_window_hours
        ),
        topic_edit_window_hours=(
            configuration.discussions.topic_edit_window_hours
        ),
    )


def build_chat_peer(user: User) -> ChatPeerResponse:
    """
    Собеседник для списка/шапки чата.

    Args:
        user: ORM User собеседника.

    Returns:
        ChatPeerResponse.
    """
    return ChatPeerResponse(
        uid=user.uid,
        display_name=user.display_name,
        username=user.username,
        initials=user.initials,
        avatar_url=_resolve_avatar_url(user),
        has_avatar=_user_has_avatar(user),
    )


def build_chat_last_message(
    message: DirectMessage | None,
) -> ChatLastMessageResponse | None:
    """
    Превью последнего сообщения.

    Args:
        message: ORM DirectMessage или None.

    Returns:
        ChatLastMessageResponse или None.
    """
    if message is None:
        return None
    return ChatLastMessageResponse(
        id=message.id,
        body=strip_message_tags(message.body),
        kind=message.kind,
        created_at=message.created_at,
        sender_id=message.sender_id,
    )


def build_chat_item(
    chat: DirectChat,
    *,
    current_user_uid: uuid.UUID,
    last_message: DirectMessage | None = None,
    unread_count: int = 0,
) -> ChatItemResponse:
    """
    Элемент списка диалогов.

    Args:
        chat: ORM DirectChat с user_low/user_high.
        current_user_uid: uid текущего пользователя.
        last_message: последнее сообщение (опционально).
        unread_count: непрочитанные входящие в диалоге.

    Returns:
        ChatItemResponse.
    """
    peer = (
        chat.user_high
        if chat.user_low_id == current_user_uid
        else chat.user_low
    )
    return ChatItemResponse(
        id=chat.id,
        peer=build_chat_peer(peer),
        last_message=build_chat_last_message(last_message),
        updated_at=chat.updated_at,
        unread_count=max(0, int(unread_count or 0)),
    )


def build_chat_message(
    message: DirectMessage,
    *,
    current_user_uid: uuid.UUID,
) -> ChatMessageResponse:
    """
    Одно сообщение диалога.

    Args:
        message: ORM DirectMessage.
        current_user_uid: uid текущего пользователя
            (для флага is_mine).

    Returns:
        ChatMessageResponse.
    """
    return ChatMessageResponse(
        id=message.id,
        chat_id=message.chat_id,
        sender_id=message.sender_id,
        body=message.body,
        kind=message.kind,
        created_at=message.created_at,
        is_mine=message.sender_id == current_user_uid,
        read_at=message.read_at,
    )


def build_topic_notification_item(
    notification: TopicNotification,
    *,
    parent_post_id: int | None = None,
    roots_page: int = 1,
    replies_page: int | None = None,
) -> TopicNotificationItemResponse:
    """
    Элемент списка уведомлений в header.

    Args:
        notification: ORM TopicNotification с actor/topic.
        parent_post_id: id корневого поста для перехода.
        roots_page: страница корневых сообщений темы.
        replies_page: страница ответов или None.

    Returns:
        TopicNotificationItemResponse.
    """
    actor = notification.actor
    actor_name = (
        actor.display_name
        if actor is not None
        else 'Пользователь'
    )
    topic_title = (
        notification.topic.title
        if notification.topic is not None
        else 'тема'
    )
    if notification.kind == 'quote':
        action = 'процитировал(а)'
    else:
        action = 'ответил(а) на'
    text = (
        f'{actor_name} {action} ваше сообщение '
        f'в теме «{topic_title}»'
    )
    return TopicNotificationItemResponse(
        id=notification.id,
        kind=notification.kind,
        actor_uid=notification.actor_id,
        actor_display_name=actor_name,
        topic_id=notification.topic_id,
        topic_title=topic_title,
        post_id=notification.post_id,
        source_post_id=notification.source_post_id,
        parent_post_id=parent_post_id,
        roots_page=roots_page,
        replies_page=replies_page,
        text=text,
        created_at=notification.created_at,
    )


def build_chat_messages_page(
    chat: DirectChat,
    messages: list[DirectMessage],
    *,
    current_user_uid: uuid.UUID,
    has_more: bool,
) -> ChatMessagesPageResponse:
    """
    Страница сообщений с метаданными чата.

    Args:
        chat: ORM DirectChat с user_low/user_high.
        messages: сообщения текущей порции.
        current_user_uid: uid текущего пользователя.
        has_more: есть ли более старые сообщения.

    Returns:
        ChatMessagesPageResponse.
    """
    peer = (
        chat.user_high
        if chat.user_low_id == current_user_uid
        else chat.user_low
    )
    return ChatMessagesPageResponse(
        chat_id=chat.id,
        peer=build_chat_peer(peer),
        items=[
            build_chat_message(
                message,
                current_user_uid=current_user_uid,
            )
            for message in messages
        ],
        has_more=has_more,
    )
