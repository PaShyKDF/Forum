import { API_BASE_URL } from '../config.js';

const formatDateTime = (value) => {
  if (!value) {
    return '';
  }
  let raw = String(value);
  // Naive datetime из API — UTC без суффикса зоны
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

const mapTopicRow = (topic) => ({
  id: topic.id,
  title: topic.title,
  description: topic.description || '',
  topics: 1,
  posts: topic.posts_count ?? 0,
  position: topic.position ?? 99,
  isTopic: true,
  isRestricted: Boolean(topic.is_restricted),
  canManage: Boolean(topic.can_manage),
  lastPost: topic.last_post
    ? {
        title: topic.last_post.title,
        author: topic.last_post.author,
        authorUid: topic.last_post.author_uid || null,
        time: formatDateTime(topic.last_post.created_at),
        topicId: topic.last_post.topic_id ?? topic.id,
      }
    : {
        title: topic.title,
        author: '—',
        authorUid: null,
        time: '',
        topicId: topic.id,
      },
});

const mapCategoryRow = (category) => ({
  id: category.id,
  title: category.title,
  description: category.description || '',
  topics: category.topics_count ?? 0,
  posts: category.posts_count ?? 0,
  position: category.position ?? 99,
  isTopic: false,
  isCategory: true,
  isRestricted: Boolean(category.is_restricted),
  canManage: Boolean(category.can_manage),
  lastPost: category.last_post
    ? {
        title: category.last_post.title,
        author: category.last_post.author,
        authorUid: category.last_post.author_uid || null,
        time: formatDateTime(category.last_post.created_at),
        topicId: category.last_post.topic_id ?? null,
      }
    : {
        title: '—',
        author: '—',
        authorUid: null,
        time: '',
        topicId: null,
      },
});

const mapAccessMember = (member) => ({
  uid: member.uid,
  username: member.username,
  displayName: member.display_name,
  initials: member.initials,
  avatarUrl: member.avatar_url || null,
});

const mapSectionWithCategories = (section) => ({
  id: section.id,
  title: section.title,
  position: section.position ?? 99,
  isTopic: Boolean(section.is_topic),
  categories: (section.categories || []).map(mapCategoryRow),
});

const mapQuotedPost = (quoted) => {
  if (!quoted) {
    return null;
  }
  return {
    id: quoted.id,
    bodySnippet: quoted.body_snippet || '',
    author: quoted.author_display_name || '',
    authorUid: quoted.author_uid || null,
    jumpTarget: quoted.jump_target || `#post-${quoted.id}`,
  };
};

const mapPost = (post) => ({
  id: post.id,
  body: post.body,
  text: post.body,
  createdAt: post.created_at,
  updatedAt: post.updated_at,
  date: formatDateTime(post.created_at),
  isTopicStarter: Boolean(post.is_topic_starter),
  replyToPostId: post.reply_to_post_id ?? null,
  isRoot: post.reply_to_post_id == null,
  quotedPost: mapQuotedPost(post.quoted_post),
  repliesCount: post.replies_count ?? 0,
  canEdit: Boolean(post.can_edit),
  author: post.author?.display_name || '',
  authorUid: post.author?.uid || null,
  initials: post.author?.initials || '?',
  avatarUrl: post.author?.avatar_url || null,
});

const mapPaginatedPosts = (payload) => ({
  items: (payload.items || []).map(mapPost),
  page: payload.page || 1,
  pageSize: payload.page_size || 20,
  total: payload.total || 0,
  totalPages: payload.total_pages || 0,
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

export const forumApi = {
  async getHome() {
    const home = await request('/api/home');
    const special = (home.special_sections || []).map(
      mapSectionWithCategories,
    );
    const regular = (home.sections || []).map(
      mapSectionWithCategories,
    );
    return {
      sections: [...special, ...regular],
      communityMembersCount:
        home.community_members_count ?? 0,
      todayActiveMembersCount:
        home.today_active_members_count ?? 0,
    };
  },

  async getSection(id) {
    const section = await request(`/api/sections/${id}`);
    return {
      id: section.id,
      title: section.title,
      isTopic: Boolean(section.is_topic),
      categories: (section.categories || []).map(
        mapCategoryRow,
      ),
    };
  },

  async getTopic(id, { page = 1, pageSize } = {}) {
    const params = new URLSearchParams();
    params.set('page', String(page));
    if (pageSize) {
      params.set('page_size', String(pageSize));
    }
    const topic = await request(
      `/api/topics/${id}?${params.toString()}`,
    );
    return {
      id: topic.id,
      title: topic.title,
      description: topic.description || '',
      section: topic.section?.title || '',
      sectionId: topic.section?.id,
      category: topic.category?.title || '',
      categoryId: topic.category?.id,
      isClosed: Boolean(topic.is_closed),
      isRestricted: Boolean(topic.is_restricted),
      canManage: Boolean(topic.can_manage),
      canEditTitle: Boolean(topic.can_edit_title),
      postEditWindowHours: topic.post_edit_window_hours ?? 24,
      topicEditWindowHours:
        topic.topic_edit_window_hours ?? 24,
      posts: mapPaginatedPosts(topic.posts || {}),
    };
  },

  async updateTopicTitle(topicId, title) {
    return request(`/api/topics/${topicId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    });
  },

  async getTopicPosts(topicId, { page = 1, pageSize } = {}) {
    const params = new URLSearchParams();
    params.set('page', String(page));
    if (pageSize) {
      params.set('page_size', String(pageSize));
    }
    const payload = await request(
      `/api/topics/${topicId}/posts?${params.toString()}`,
    );
    return mapPaginatedPosts(payload);
  },

  async getPostReplies(postId, { page = 1, pageSize } = {}) {
    const params = new URLSearchParams();
    params.set('page', String(page));
    if (pageSize) {
      params.set('page_size', String(pageSize));
    }
    const payload = await request(
      `/api/posts/${postId}/replies?${params.toString()}`,
    );
    return mapPaginatedPosts(payload);
  },

  async createTopicPost(topicId, body, quotedPostId = null) {
    const payload = { body };
    if (quotedPostId != null) {
      payload.quoted_post_id = quotedPostId;
    }
    const post = await request(
      `/api/topics/${topicId}/posts`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    );
    return mapPost(post);
  },

  async createReply(postId, body, quotedPostId = null) {
    const payload = { body };
    if (quotedPostId != null) {
      payload.quoted_post_id = quotedPostId;
    }
    const post = await request(
      `/api/posts/${postId}/replies`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    );
    return mapPost(post);
  },

  async updatePost(postId, body, quotedPostId = null) {
    const post = await request(`/api/posts/${postId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        body,
        quoted_post_id: quotedPostId,
      }),
    });
    return mapPost(post);
  },

  async getTopics(filter) {
    const params = new URLSearchParams();
    if (filter === 'active' || filter === 'participated') {
      params.set('filter', filter);
    }
    const query = params.toString();
    const path = query
      ? `/api/topics?${query}`
      : '/api/topics';
    const topics = await request(path);
    return topics.map(mapTopicRow);
  },

  async getForum(id) {
    const category = await request(`/api/categories/${id}`);
    return {
      id: category.id,
      title: category.title,
      description: category.description || '',
      section: category.section?.title || '',
      sectionId: category.section?.id,
      isRestricted: Boolean(category.is_restricted),
      canManage: Boolean(category.can_manage),
      topicList: (category.topics || []).map(mapTopicRow),
    };
  },

  async createTopic(
    categoryId,
    {
      title,
      body,
      description,
      isRestricted = false,
      allowedUserUids = [],
    },
  ) {
    const payload = {
      title,
      body,
      is_restricted: Boolean(isRestricted),
      allowed_user_uids: allowedUserUids,
    };
    if (description != null && description !== '') {
      payload.description = description;
    }
    return request(`/api/categories/${categoryId}/topics`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async createCategory(
    sectionId,
    {
      title,
      description,
      isRestricted = false,
      allowedUserUids = [],
    },
  ) {
    const payload = {
      title,
      is_restricted: Boolean(isRestricted),
      allowed_user_uids: allowedUserUids,
    };
    if (description != null && description !== '') {
      payload.description = description;
    }
    return request(
      `/api/sections/${sectionId}/categories`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    );
  },

  async searchUsers(query = '', limit = 30) {
    const params = new URLSearchParams();
    params.set('q', query || '');
    params.set('limit', String(limit));
    const users = await request(
      `/api/users/search?${params.toString()}`,
    );
    return (users || []).map((user) => ({
      uid: user.uid,
      username: user.username,
      displayName: user.display_name,
      initials: user.initials,
      avatarUrl: user.avatar_url || null,
    }));
  },

  async getCategoryMembers(categoryId) {
    const members = await request(
      `/api/categories/${categoryId}/members`,
    );
    return (members || []).map(mapAccessMember);
  },

  async setCategoryMembers(categoryId, userUids) {
    const members = await request(
      `/api/categories/${categoryId}/members`,
      {
        method: 'PUT',
        body: JSON.stringify({ user_uids: userUids }),
      },
    );
    return (members || []).map(mapAccessMember);
  },

  async setCategoryVisibility(categoryId, isRestricted) {
    return request(
      `/api/categories/${categoryId}/visibility`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          is_restricted: Boolean(isRestricted),
        }),
      },
    );
  },

  async getTopicMembers(topicId) {
    const members = await request(
      `/api/topics/${topicId}/members`,
    );
    return (members || []).map(mapAccessMember);
  },

  async setTopicMembers(topicId, userUids) {
    const members = await request(
      `/api/topics/${topicId}/members`,
      {
        method: 'PUT',
        body: JSON.stringify({ user_uids: userUids }),
      },
    );
    return (members || []).map(mapAccessMember);
  },

  async setTopicVisibility(topicId, isRestricted) {
    return request(`/api/topics/${topicId}/visibility`, {
      method: 'PATCH',
      body: JSON.stringify({
        is_restricted: Boolean(isRestricted),
      }),
    });
  },

  async getUserProfile(userUid) {
    return request(`/api/users/${userUid}`);
  },

  async getContactPage() {
    const payload = await request('/api/contact');
    return {
      title: payload.title || 'Связаться',
      bio: payload.bio || '',
      photoUrl: payload.photo_url || '',
      telegramUrl: payload.telegram_url || '',
      whatsappUrl: payload.whatsapp_url || '',
    };
  },

  async submitSupportTicket({ subject, body, email }) {
    return request('/api/support/tickets', {
      method: 'POST',
      body: JSON.stringify({
        subject,
        body,
        email: email || null,
      }),
    });
  },
};
