from collections.abc import Callable

from forum.domain import commands, events
from forum.service_layer.handlers.acl import (
    handle_get_category_members_command,
    handle_get_topic_members_command,
    handle_search_users_command,
    handle_set_category_members_command,
    handle_set_category_visibility_command,
    handle_set_topic_members_command,
    handle_set_topic_visibility_command,
)
from forum.service_layer.handlers.auth import (
    handle_ensure_user_command,
)
from forum.service_layer.handlers.categories import (
    handle_create_category_command,
    handle_get_categories_command,
    handle_get_category_by_id_command,
    handle_get_home_command,
)
from forum.service_layer.handlers.chats import (
    handle_get_chat_messages_command,
    handle_get_my_chats_command,
    handle_get_or_create_direct_chat_command,
    handle_send_direct_message_command,
)
from forum.service_layer.handlers.notifications import (
    handle_clear_notifications_command,
    handle_dismiss_notification_command,
    handle_get_my_notifications_command,
    handle_get_unread_chat_count_command,
    handle_mark_chat_messages_visible_command,
    handle_mark_notification_read_command,
)
from forum.service_layer.handlers.posts import (
    handle_create_reply_command,
    handle_create_topic_post_command,
    handle_get_post_replies_command,
    handle_get_topic_posts_command,
    handle_update_post_command,
)
from forum.service_layer.handlers.sections import (
    handle_get_section_by_id_command,
    handle_get_sections_command,
)
from forum.service_layer.handlers.support import (
    handle_create_support_ticket_command,
)
from forum.service_layer.handlers.test import (
    handle_echo_test_command,
    handle_echo_test_processed,
)
from forum.service_layer.handlers.topics import (
    handle_create_topic_command,
    handle_get_topic_by_id_command,
    handle_get_topics_command,
    handle_update_topic_title_command,
)
from forum.service_layer.handlers.users import (
    handle_delete_user_avatar_command,
    handle_get_current_user_profile_command,
    handle_get_public_user_profile_command,
    handle_get_user_avatar_command,
    handle_update_user_profile_command,
    handle_upload_user_avatar_command,
)
from forum.service_layer.handlers.visitors import (
    handle_track_guest_visit_command,
)


def get_event_handlers() -> dict[
    type[events.Event],
    list[Callable],
]:
    """
    Реестр обработчиков доменных событий.

    Returns:
        Словарь: тип Event → список callable-handler'ов.
    """
    return {
        events.EchoTestProcessed: [handle_echo_test_processed],
    }


def get_command_handlers() -> dict[
    type[commands.Command],
    Callable,
]:
    """
    Реестр обработчиков доменных команд.

    Returns:
        Словарь: тип Command → callable-handler.
    """
    return {
        commands.EchoTestCommand: handle_echo_test_command,
        commands.EnsureUserCommand: handle_ensure_user_command,
        commands.TrackGuestVisitCommand: (
            handle_track_guest_visit_command
        ),
        commands.GetHomeCommand: handle_get_home_command,
        commands.GetSectionsCommand: (
            handle_get_sections_command
        ),
        commands.GetSectionByIdCommand: (
            handle_get_section_by_id_command
        ),
        commands.GetCategoriesCommand: (
            handle_get_categories_command
        ),
        commands.GetCategoryByIdCommand: (
            handle_get_category_by_id_command
        ),
        commands.CreateCategoryCommand: (
            handle_create_category_command
        ),
        commands.GetTopicsCommand: handle_get_topics_command,
        commands.GetTopicByIdCommand: (
            handle_get_topic_by_id_command
        ),
        commands.CreateTopicCommand: (
            handle_create_topic_command
        ),
        commands.UpdateTopicTitleCommand: (
            handle_update_topic_title_command
        ),
        commands.GetTopicPostsCommand: (
            handle_get_topic_posts_command
        ),
        commands.GetPostRepliesCommand: (
            handle_get_post_replies_command
        ),
        commands.CreateTopicPostCommand: (
            handle_create_topic_post_command
        ),
        commands.CreateReplyCommand: (
            handle_create_reply_command
        ),
        commands.UpdatePostCommand: handle_update_post_command,
        commands.GetCurrentUserProfileCommand: (
            handle_get_current_user_profile_command
        ),
        commands.GetPublicUserProfileCommand: (
            handle_get_public_user_profile_command
        ),
        commands.UpdateUserProfileCommand: (
            handle_update_user_profile_command
        ),
        commands.UploadUserAvatarCommand: (
            handle_upload_user_avatar_command
        ),
        commands.DeleteUserAvatarCommand: (
            handle_delete_user_avatar_command
        ),
        commands.GetUserAvatarCommand: (
            handle_get_user_avatar_command
        ),
        commands.GetOrCreateDirectChatCommand: (
            handle_get_or_create_direct_chat_command
        ),
        commands.GetMyChatsCommand: (
            handle_get_my_chats_command
        ),
        commands.GetChatMessagesCommand: (
            handle_get_chat_messages_command
        ),
        commands.SendDirectMessageCommand: (
            handle_send_direct_message_command
        ),
        commands.GetMyNotificationsCommand: (
            handle_get_my_notifications_command
        ),
        commands.MarkNotificationReadCommand: (
            handle_mark_notification_read_command
        ),
        commands.DismissNotificationCommand: (
            handle_dismiss_notification_command
        ),
        commands.ClearNotificationsCommand: (
            handle_clear_notifications_command
        ),
        commands.GetUnreadChatCountCommand: (
            handle_get_unread_chat_count_command
        ),
        commands.MarkChatMessagesVisibleCommand: (
            handle_mark_chat_messages_visible_command
        ),
        commands.CreateSupportTicketCommand: (
            handle_create_support_ticket_command
        ),
        commands.GetCategoryMembersCommand: (
            handle_get_category_members_command
        ),
        commands.SetCategoryMembersCommand: (
            handle_set_category_members_command
        ),
        commands.GetTopicMembersCommand: (
            handle_get_topic_members_command
        ),
        commands.SetTopicMembersCommand: (
            handle_set_topic_members_command
        ),
        commands.SetCategoryVisibilityCommand: (
            handle_set_category_visibility_command
        ),
        commands.SetTopicVisibilityCommand: (
            handle_set_topic_visibility_command
        ),
        commands.SearchUsersCommand: (
            handle_search_users_command
        ),
    }
