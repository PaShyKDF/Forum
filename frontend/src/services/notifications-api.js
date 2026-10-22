import { API_BASE_URL } from '../config.js';

const formatDateTime = (value) => {
  if (!value) {
    return '';
  }
  let raw = String(value);
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw);
  if (
    /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(raw) &&
    !hasZone
  ) {
    raw = `${raw.replace(' ', 'T')}Z`;
  }
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Moscow',
  }).format(date);
};

const mapNotification = (item) => ({
  id: item.id,
  kind: item.kind,
  actorUid: item.actor_uid,
  actorDisplayName: item.actor_display_name || '',
  topicId: item.topic_id,
  topicTitle: item.topic_title || '',
  postId: item.post_id,
  sourcePostId: item.source_post_id,
  parentPostId: item.parent_post_id ?? null,
  rootsPage: item.roots_page || 1,
  repliesPage: item.replies_page ?? null,
  text: item.text || '',
  createdAt: item.created_at,
  time: formatDateTime(item.created_at),
});

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(options.body
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...(options.headers || {}),
    },
    ...options,
  });

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    const detail =
      (data && (data.detail || data.message)) ||
      response.statusText;
    const message = Array.isArray(detail)
      ? detail
          .map((item) => item.msg || JSON.stringify(item))
          .join('; ')
      : String(detail);
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return data;
}

export const notificationsApi = {
  async list() {
    const payload = await request('/api/notifications');
    return {
      items: (payload.items || []).map(mapNotification),
      unreadCount: Number(payload.unread_count || 0),
    };
  },

  async markRead(notificationId) {
    return request(
      `/api/notifications/${notificationId}/read`,
      { method: 'POST' },
    );
  },

  async dismiss(notificationId) {
    return request(
      `/api/notifications/${notificationId}`,
      { method: 'DELETE' },
    );
  },

  async clearAll() {
    return request('/api/notifications/clear', {
      method: 'POST',
    });
  },

  async getUnreadChatCount() {
    const payload = await request('/api/chats/unread-count');
    return Number(payload.unread_count || 0);
  },

  async markChatMessagesVisible(messageIds) {
    const payload = await request(
      '/api/chats/messages/mark-visible',
      {
        method: 'POST',
        body: JSON.stringify({
          message_ids: messageIds,
        }),
      },
    );
    return {
      markedIds: payload.marked_ids || [],
      unreadCount: Number(payload.unread_count || 0),
    };
  },
};
