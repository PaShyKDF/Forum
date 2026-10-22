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

const mapPeer = (peer) => ({
  uid: peer.uid,
  displayName: peer.display_name || peer.username || '',
  username: peer.username || '',
  initials: peer.initials || '?',
  avatarUrl: peer.avatar_url || null,
  hasAvatar: Boolean(peer.has_avatar),
});

const mapLastMessage = (message) => {
  if (!message) {
    return null;
  }
  return {
    id: message.id,
    body: message.body || '',
    kind: message.kind || 'text',
    createdAt: message.created_at,
    time: formatDateTime(message.created_at),
    senderId: message.sender_id,
  };
};

const mapChatItem = (chat) => ({
  id: chat.id,
  peer: mapPeer(chat.peer || {}),
  lastMessage: mapLastMessage(chat.last_message),
  updatedAt: chat.updated_at,
  updatedTime: formatDateTime(chat.updated_at),
  unreadCount: Number(chat.unread_count || 0),
});

const mapMessage = (message) => ({
  id: message.id,
  chatId: message.chat_id,
  senderId: message.sender_id,
  body: message.body || '',
  kind: message.kind || 'text',
  createdAt: message.created_at,
  time: formatDateTime(message.created_at),
  isMine: Boolean(message.is_mine),
  readAt: message.read_at || null,
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

export const chatsApi = {
  async getMyChats() {
    const chats = await request('/api/chats');
    return (chats || []).map(mapChatItem);
  },

  async getOrCreateDirectChat(userUid) {
    const chat = await request(
      `/api/chats/direct/${userUid}`,
      { method: 'POST' },
    );
    return mapChatItem(chat);
  },

  async getChatMessages(chatId, { limit = 50, beforeId } = {}) {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    if (beforeId != null) {
      params.set('before_id', String(beforeId));
    }
    const payload = await request(
      `/api/chats/${chatId}/messages?${params.toString()}`,
    );
    return {
      chatId: payload.chat_id,
      peer: mapPeer(payload.peer || {}),
      items: (payload.items || []).map(mapMessage),
      hasMore: Boolean(payload.has_more),
    };
  },

  async sendMessage(chatId, body) {
    const message = await request(
      `/api/chats/${chatId}/messages`,
      {
        method: 'POST',
        body: JSON.stringify({ body }),
      },
    );
    return mapMessage(message);
  },
};
