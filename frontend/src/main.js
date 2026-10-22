import { authApi } from './services/auth-api.js';
import { chatsApi } from './services/chats-api.js';
import { forumApi } from './services/forum-api.js';
import { notificationsApi } from './services/notifications-api.js';
import { rulesSections } from './content/rules.js';
import {
  chatListItemTemplate,
  chatsPageTemplate,
  contactTemplate,
  forumTemplate,
  homeTemplate,
  listTemplate,
  notFoundTemplate,
  paginationTemplate,
  postCardTemplate,
  profileTemplate,
  publicProfileTemplate,
  repliesBlockTemplate,
  rulesTemplate,
  sectionTemplate,
  supportTemplate,
  topicTemplate,
} from './ui/templates.js';
import {
  clearEditor,
  findEditorSurface,
  getEditorHtml,
  hideRichToolbar,
  initRichTextEditor,
  isEditorEmpty,
  renderFormattedBody,
} from './ui/rich-text.js';

function readRichBody(container) {
  const surface = findEditorSurface(container);
  if (surface) {
    const html = getEditorHtml(surface);
    return isEditorEmpty(html) ? '' : html;
  }
  return (
    container?.querySelector('textarea')?.value?.trim() || ''
  );
}

const app = document.querySelector('#app');
const loginButton = document.querySelector(
  '.header__actions .login-button',
);
const headerUser = document.querySelector('.header-user');
const headerUserName = document.querySelector('.header-user__name');
const headerUserAvatar = document.querySelector(
  '.header-user__avatar',
);
const headerLogoutButton = document.querySelector(
  '.header-user__logout',
);

let currentUser = null;
let topicState = null;
let chatState = null;
let chatPollTimer = null;
let notificationsState = {
  items: [],
  unreadCount: 0,
  chatUnreadCount: 0,
};
let pendingPostJump = null;
let chatReadObserver = null;
let chatReadPending = new Set();
let chatReadFlushTimer = null;

const CHAT_POLL_MS = 4000;

function stopChatPolling() {
  if (chatPollTimer) {
    clearInterval(chatPollTimer);
    chatPollTimer = null;
  }
}

function startChatPolling(chatId) {
  stopChatPolling();
  chatPollTimer = setInterval(() => {
    void refreshActiveChat(chatId, { silent: true });
  }, CHAT_POLL_MS);
}

const routes = {
  '/': async () =>
    homeTemplate(await forumApi.getHome(), {
      isAuthenticated: Boolean(currentUser),
      isAdmin: Boolean(currentUser?.is_admin),
    }),
  '/active': async () =>
    listTemplate(
      'Активные темы',
      await forumApi.getTopics('active'),
    ),
  '/participated': async () =>
    listTemplate(
      'С вашим участием',
      await forumApi.getTopics('participated'),
    ),
  '/search': async () => listTemplate('Поиск по форуму', []),
  '/profile': async () =>
    profileTemplate(await authApi.getProfile()),
  '/rules': async () => rulesTemplate(rulesSections),
  '/contact': async () =>
    contactTemplate(await forumApi.getContactPage()),
  '/support': async () => {
    const email = currentUser?.email || '';
    const emailLocked = Boolean(currentUser);
    const emailMissing = Boolean(currentUser) && !email;
    return supportTemplate({
      email,
      emailLocked,
      emailMissing,
    });
  },
};

const scrollPositions = new Map();
let historyNavigation = false;

const currentPath = () => {
  let path = location.hash.replace(/^#/, '') || '/';
  path = path.split('?')[0];
  if (!path.startsWith('/')) {
    path = `/${path}`;
  }
  if (path.length > 1 && path.endsWith('/')) {
    path = path.slice(0, -1);
  }
  return path;
};

const currentQuery = () => {
  const raw = location.hash.replace(/^#/, '') || '/';
  const qIndex = raw.indexOf('?');
  if (qIndex < 0) {
    return new URLSearchParams();
  }
  return new URLSearchParams(raw.slice(qIndex + 1));
};

const formatBadgeCount = (count) => {
  const value = Number(count) || 0;
  if (value <= 0) {
    return '';
  }
  return value > 20 ? '20+' : String(value);
};

function setBadge(node, count) {
  if (!node) {
    return;
  }
  const label = formatBadgeCount(count);
  if (!label) {
    node.hidden = true;
    node.textContent = '0';
    return;
  }
  node.hidden = false;
  node.textContent = label;
}

function updateHeaderBadges() {
  setBadge(
    document.querySelector('[data-notify-badge]'),
    notificationsState.unreadCount,
  );
  setBadge(
    document.querySelector('[data-chats-badge]'),
    notificationsState.chatUnreadCount,
  );
}

function renderNotifyList() {
  const list = document.querySelector('[data-notify-list]');
  if (!list) {
    return;
  }
  const items = notificationsState.items || [];
  if (!items.length) {
    list.innerHTML =
      '<p class="notify-panel__empty">Нет новых уведомлений</p>';
    return;
  }
  list.innerHTML = items
    .map(
      (item) => `<div class="notify-item">
        <button
          class="notify-item__body"
          type="button"
          data-action="open-notification"
          data-notify-id="${item.id}"
        >
          <p class="notify-item__text"></p>
          <p class="notify-item__meta"></p>
        </button>
        <button
          class="notify-item__dismiss"
          type="button"
          data-action="dismiss-notification"
          data-notify-id="${item.id}"
          aria-label="Удалить уведомление"
          title="Удалить"
        >×</button>
      </div>`,
    )
    .join('');
  list
    .querySelectorAll('[data-action="open-notification"]')
    .forEach((node) => {
      const id = Number(node.dataset.notifyId);
      const item = items.find((entry) => entry.id === id);
      if (!item) {
        return;
      }
      const text = node.querySelector('.notify-item__text');
      const meta = node.querySelector('.notify-item__meta');
      if (text) {
        text.textContent = item.text;
      }
      if (meta) {
        meta.textContent = item.time || '';
      }
    });
}

function setNotifyPanelOpen(open) {
  const panel = document.querySelector('[data-notify-panel]');
  const toggle = document.querySelector('[data-notify-toggle]');
  if (!panel || !toggle) {
    return;
  }
  panel.hidden = !open;
  toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
}

async function refreshNotifications() {
  if (!currentUser) {
    notificationsState = {
      items: [],
      unreadCount: 0,
      chatUnreadCount: 0,
    };
    updateHeaderBadges();
    renderNotifyList();
    setNotifyPanelOpen(false);
    return;
  }
  try {
    const [notify, chatUnread] = await Promise.all([
      notificationsApi.list(),
      notificationsApi.getUnreadChatCount(),
    ]);
    notificationsState = {
      items: notify.items,
      unreadCount: notify.unreadCount,
      chatUnreadCount: chatUnread,
    };
  } catch (error) {
    console.error(error);
  }
  updateHeaderBadges();
  renderNotifyList();
}

function updateHeaderAuth() {
  if (!loginButton || !headerUser || !headerUserName) {
    return;
  }
  document.querySelectorAll('[data-auth-only]').forEach(
    (node) => {
      node.hidden = !currentUser;
    },
  );
  if (currentUser) {
    if (typeof currentUser.is_admin !== 'boolean') {
      currentUser.is_admin = Boolean(currentUser.is_admin);
    }
    const name =
      currentUser.display_name || currentUser.username;
    headerUserName.textContent = name;
    headerUserName.setAttribute('title', 'Мой профиль');
    headerUserName.setAttribute('aria-label', 'Мой профиль');
    if (headerUserAvatar) {
      if (currentUser.has_avatar && currentUser.avatar_url) {
        headerUserAvatar.src =
          `${currentUser.avatar_url}?t=${Date.now()}`;
        headerUserAvatar.hidden = false;
      } else {
        headerUserAvatar.removeAttribute('src');
        headerUserAvatar.hidden = true;
      }
    }
    headerUser.hidden = false;
    loginButton.hidden = true;
  } else {
    headerUser.hidden = true;
    if (headerUserAvatar) {
      headerUserAvatar.removeAttribute('src');
      headerUserAvatar.hidden = true;
    }
    loginButton.hidden = false;
    loginButton.textContent = 'Войти';
    loginButton.dataset.auth = 'guest';
    loginButton.setAttribute(
      'href',
      authApi.startUrl(location.hash || '#/'),
    );
    loginButton.setAttribute('title', 'Войти');
    loginButton.setAttribute('aria-label', 'Войти');
    setNotifyPanelOpen(false);
  }
  updateHeaderBadges();
}

async function refreshSession() {
  try {
    const session = await authApi.me();
    currentUser = session.user;
  } catch {
    currentUser = null;
  }
  updateHeaderAuth();
  await refreshNotifications();
}

function showError(container, message) {
  if (!container) {
    return;
  }
  const errorNode = container.querySelector('[data-error]');
  if (!errorNode) {
    return;
  }
  errorNode.hidden = !message;
  errorNode.textContent = message || '';
}

function renderQuotePreview(container, quote) {
  const preview = container?.querySelector(
    '[data-quote-preview]',
  );
  if (!preview) {
    return;
  }
  if (!quote) {
    preview.hidden = true;
    preview.innerHTML = '';
    if (container) {
      delete container.dataset.quotedPostId;
    }
    return;
  }
  container.dataset.quotedPostId = String(quote.id);
  preview.hidden = false;
  preview.innerHTML = `
    <div class="quote-preview__card">
      <div>
        <b>${quote.author || 'Участник'}</b>
        <p>${quote.bodySnippet || quote.body || ''}</p>
      </div>
      <button type="button" class="button button--soft" data-action="clear-quote">Убрать</button>
    </div>
  `;
}

function quoteFromPostEl(postEl) {
  if (!postEl) {
    return null;
  }
  const text =
    postEl.querySelector('[data-post-text]')?.textContent ||
    '';
  const author =
    postEl.querySelector('aside .user-link b')?.textContent ||
    postEl.querySelector('aside b')?.textContent ||
    '';
  const snippet =
    text.length > 140 ? `${text.slice(0, 137)}...` : text;
  return {
    id: Number(postEl.dataset.postId),
    author,
    bodySnippet: snippet,
  };
}

function setComposeVisible(visible) {
  const form = document.querySelector('[data-compose-root]');
  if (!form) {
    return;
  }
  form.classList.toggle('is-open', visible);
  if (visible) {
    findEditorSurface(form)?.focus();
  } else {
    clearEditor(findEditorSurface(form));
    hideRichToolbar();
    renderQuotePreview(form, null);
  }
}

function renderQuotedBlock(postEl, quoted) {
  const body = postEl.querySelector('.post__body');
  if (!body) {
    return;
  }
  body.querySelector('.post-quote')?.remove();
  if (!quoted) {
    postEl.dataset.quotedId = '';
    return;
  }
  postEl.dataset.quotedId = String(quoted.id);
  const meta = body.querySelector('.post__meta');
  const block = document.createElement('div');
  block.className = 'post-quote';
  const authorEl = quoted.authorUid
    ? document.createElement('a')
    : document.createElement('span');
  authorEl.className = quoted.authorUid
    ? 'post-quote__author user-link'
    : 'post-quote__author';
  if (quoted.authorUid) {
    authorEl.href = `#/users/${quoted.authorUid}`;
  }
  authorEl.textContent = quoted.author || '';
  const textLink = document.createElement('a');
  textLink.className = 'post-quote__text';
  textLink.href = quoted.jumpTarget || `#post-${quoted.id}`;
  textLink.dataset.action = 'jump-quote';
  textLink.dataset.quoteId = String(quoted.id);
  textLink.textContent = quoted.bodySnippet || '';
  block.appendChild(authorEl);
  block.appendChild(textLink);
  meta?.after(block);
}

function renderRoots(pageData) {
  const roots = document.querySelector('[data-roots]');
  const paginationHost = document.querySelector(
    '[data-roots-pagination]',
  );
  if (!roots || !topicState) {
    return;
  }
  topicState.posts = pageData;
  roots.innerHTML =
    pageData.items
      .map((post) => postCardTemplate(post))
      .join('') ||
    '<p class="replies__empty">Пока нет сообщений. Будьте первым!</p>';
  initRichTextEditor(roots);
  if (paginationHost) {
    paginationHost.innerHTML = paginationTemplate({
      page: pageData.page,
      totalPages: pageData.totalPages,
      total: pageData.total,
      prefix: 'roots',
    });
  }
}

async function loadTopicPage(topicId, page = 1) {
  const topic = await forumApi.getTopic(topicId, { page });
  topicState = {
    id: topic.id,
    title: topic.title,
    isClosed: topic.isClosed,
    canEditTitle: Boolean(topic.canEditTitle),
    posts: topic.posts,
    repliesCache: new Map(),
  };
  return topicTemplate(topic, {
    isAuthenticated: Boolean(currentUser),
  });
}

function scrollToPostElement(postId) {
  const target = document.getElementById(`post-${postId}`);
  if (!target) {
    return false;
  }
  target.scrollIntoView({
    behavior: 'smooth',
    block: 'center',
  });
  target.classList.add('post--flash');
  setTimeout(
    () => target.classList.remove('post--flash'),
    1200,
  );
  return true;
}

async function focusPostFromJump(jump) {
  if (!jump || !topicState) {
    return false;
  }
  const postId = Number(jump.postId);
  const parentPostId = jump.parentPostId
    ? Number(jump.parentPostId)
    : null;
  if (parentPostId) {
    const parentEl = document.querySelector(
      `[data-post-id="${parentPostId}"]`,
    );
    if (parentEl) {
      await loadReplies(
        parentEl,
        Number(jump.repliesPage) || 1,
      );
    }
  }
  return scrollToPostElement(postId);
}

async function openNotification(item) {
  if (!item) {
    return;
  }
  try {
    await notificationsApi.markRead(item.id);
  } catch (error) {
    console.error(error);
  }
  notificationsState.items = (
    notificationsState.items || []
  ).filter((entry) => entry.id !== item.id);
  notificationsState.unreadCount = Math.max(
    0,
    (notificationsState.unreadCount || 0) - 1,
  );
  updateHeaderBadges();
  renderNotifyList();
  setNotifyPanelOpen(false);

  pendingPostJump = {
    postId: item.postId,
    parentPostId: item.parentPostId,
    repliesPage: item.repliesPage || 1,
    notificationId: item.id,
  };
  const params = new URLSearchParams();
  params.set('post', String(item.postId));
  if (item.rootsPage && item.rootsPage > 1) {
    params.set('page', String(item.rootsPage));
  }
  if (item.parentPostId) {
    params.set('parent', String(item.parentPostId));
  }
  if (item.repliesPage && item.repliesPage > 1) {
    params.set('rpage', String(item.repliesPage));
  }
  location.hash =
    `#/topic/${item.topicId}?${params.toString()}`;
}

async function changeRootsPage(page) {
  if (!topicState) {
    return;
  }
  const pageData = await forumApi.getTopicPosts(topicState.id, {
    page,
  });
  renderRoots(pageData);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function loadReplies(postEl, page = 1) {
  const postId = Number(postEl.dataset.postId);
  const depth = Number(postEl.dataset.depth || 0);
  const container = postEl.querySelector('[data-replies]');
  if (!container) {
    return;
  }
  container.hidden = false;
  container.innerHTML =
    '<p class="replies__loading">Загружаем ответы…</p>';
  try {
    const pageData = await forumApi.getPostReplies(postId, {
      page,
    });
    topicState?.repliesCache.set(postId, pageData);
    container.innerHTML = repliesBlockTemplate(
      postId,
      pageData,
      { depth: depth + 1 },
    );
    initRichTextEditor(container);
    const toggle = postEl.querySelector(
      '[data-action="toggle-replies"]',
    );
    if (toggle) {
      toggle.textContent = `Скрыть ответы (${pageData.total})`;
      toggle.dataset.expanded = '1';
    }
    postEl.dataset.repliesCount = String(pageData.total);
  } catch (error) {
    container.innerHTML = `<p class="compose__error">${error.message}</p>`;
  }
}

function collapseReplies(postEl) {
  const container = postEl.querySelector('[data-replies]');
  if (container) {
    container.hidden = true;
    container.innerHTML = '';
  }
  const toggle = postEl.querySelector(
    '[data-action="toggle-replies"]',
  );
  const count = Number(postEl.dataset.repliesCount || 0);
  if (toggle) {
    toggle.dataset.expanded = '0';
    if (count > 0) {
      toggle.textContent = `Ответы (${count})`;
    } else {
      toggle.remove();
    }
  }
}

async function handleTopicClick(event) {
  const loginAction = event.target.closest(
    '[data-action="login"]',
  );
  if (loginAction) {
    event.preventDefault();
    location.href = authApi.startUrl(
      location.hash || '#/',
    );
    return;
  }

  const topicPage = event.target.closest('[data-topic-id]');
  if (!topicPage || !topicState) {
    return;
  }

  const actionBtn = event.target.closest('[data-action]');
  const pageAction = event.target.closest('[data-page-action]');

  if (
    actionBtn?.dataset.action === 'toggle-topic-visibility'
  ) {
    const topicId = Number(topicPage.dataset.topicId);
    const currentlyRestricted =
      actionBtn.dataset.restricted === '1';
    actionBtn.disabled = true;
    try {
      await forumApi.setTopicVisibility(
        topicId,
        !currentlyRestricted,
      );
      await render();
    } catch (error) {
      window.alert(error.message);
    } finally {
      actionBtn.disabled = false;
    }
    return;
  }

  if (pageAction) {
    const pagination = pageAction.closest('[data-pagination]');
    if (!pagination) {
      return;
    }
    const kind = pagination.dataset.pagination || '';
    const input = pagination.querySelector('[data-page-input]');
    let page = Number(input?.value || 1);
    if (pageAction.dataset.pageAction === 'prev') {
      page -= 1;
    } else if (pageAction.dataset.pageAction === 'next') {
      page += 1;
    } else if (pageAction.dataset.pageAction === 'go') {
      page = Number(input?.value || 1);
    }
    page = Math.max(1, page);

    if (kind === 'roots') {
      const max = topicState.posts.totalPages || 1;
      page = Math.min(page, max);
      await changeRootsPage(page);
      return;
    }
    if (kind.startsWith('replies-')) {
      const parentId = Number(kind.replace('replies-', ''));
      const parentEl = topicPage.querySelector(
        `[data-post-id="${parentId}"]`,
      );
      if (parentEl) {
        const cached = topicState.repliesCache.get(parentId);
        const max = cached?.totalPages || 1;
        page = Math.min(page, max);
        await loadReplies(parentEl, page);
      }
    }
    return;
  }

  if (!actionBtn) {
    return;
  }

  const action = actionBtn.dataset.action;
  const postEl = actionBtn.closest('[data-post-id]');

  if (action === 'open-compose') {
    setComposeVisible(true);
    return;
  }

  if (action === 'cancel-compose') {
    setComposeVisible(false);
    return;
  }

  if (action === 'open-edit-title') {
    const form = topicPage.querySelector(
      '[data-edit-title-form]',
    );
    const titleEl = topicPage.querySelector(
      '[data-topic-title]',
    );
    if (form) {
      form.hidden = false;
      topicPage.classList.add('is-editing-title');
      const input = form.querySelector('[name="title"]');
      if (input) {
        input.value = topicState.title || '';
        input.focus();
        input.select();
      }
      showError(form, '');
    }
    if (titleEl) {
      titleEl.hidden = true;
    }
    return;
  }

  if (action === 'cancel-edit-title') {
    const form = topicPage.querySelector(
      '[data-edit-title-form]',
    );
    const titleEl = topicPage.querySelector(
      '[data-topic-title]',
    );
    if (form) {
      form.hidden = true;
      topicPage.classList.remove('is-editing-title');
      showError(form, '');
      const input = form.querySelector('[name="title"]');
      if (input) {
        input.value = topicState.title || '';
      }
    }
    if (titleEl) {
      titleEl.hidden = false;
    }
    return;
  }

  if (action === 'submit-edit-title') {
    const form = topicPage.querySelector(
      '[data-edit-title-form]',
    );
    const input = form?.querySelector('[name="title"]');
    const title = input?.value?.trim() || '';
    if (!title) {
      showError(form, 'Введите название темы');
      return;
    }
    actionBtn.disabled = true;
    try {
      const updated = await forumApi.updateTopicTitle(
        topicState.id,
        title,
      );
      topicState.title = updated.title;
      topicState.canEditTitle = Boolean(
        updated.can_edit_title,
      );
      const titleEl = topicPage.querySelector(
        '[data-topic-title]',
      );
      const crumb = document.querySelector(
        '[data-topic-title-crumb]',
      );
      if (titleEl) {
        titleEl.textContent = updated.title;
        titleEl.hidden = false;
      }
      if (crumb) {
        crumb.textContent = updated.title;
      }
      if (form) {
        form.hidden = true;
        topicPage.classList.remove('is-editing-title');
        showError(form, '');
      }
      if (!updated.can_edit_title) {
        topicPage
          .querySelectorAll(
            '[data-action="open-edit-title"], [data-edit-title-form]',
          )
          .forEach((node) => node.remove());
        topicPage.dataset.canEditTitle = '0';
      }
    } catch (error) {
      showError(form, error.message);
    } finally {
      actionBtn.disabled = false;
    }
    return;
  }

  if (action === 'clear-quote') {
    const form =
      actionBtn.closest('[data-compose-root]') ||
      actionBtn.closest('[data-reply-form]') ||
      actionBtn.closest('[data-edit-form]');
    renderQuotePreview(form, null);
    return;
  }

  if (action === 'jump-quote') {
    event.preventDefault();
    const quoteId =
      actionBtn.dataset.quoteId ||
      actionBtn.getAttribute('href')?.replace('#post-', '');
    scrollToPostElement(quoteId);
    return;
  }

  if (action === 'collapse-replies' && postEl) {
    collapseReplies(postEl);
    return;
  }

  if (action === 'collapse-replies') {
    const parentId = Number(actionBtn.dataset.parentId);
    const parentEl = topicPage.querySelector(
      `[data-post-id="${parentId}"]`,
    );
    if (parentEl) {
      collapseReplies(parentEl);
      parentEl.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      });
    }
    return;
  }

  if (!postEl) {
    return;
  }

  if (action === 'quote-post') {
    if (!currentUser) {
      location.href = authApi.startUrl();
      return;
    }
    if (topicState.isClosed) {
      return;
    }
    const quote = quoteFromPostEl(postEl);
    const isRoot = postEl.dataset.isRoot === '1';
    if (isRoot) {
      setComposeVisible(true);
      const form = document.querySelector(
        '[data-compose-root]',
      );
      renderQuotePreview(form, quote);
      return;
    }
    const repliesBox = postEl.closest('[data-replies]');
    const parentEl = repliesBox?.closest(
      '[data-post-id][data-is-root="1"]',
    );
    if (!parentEl) {
      return;
    }
    const form = parentEl.querySelector('[data-reply-form]');
    if (form) {
      form.hidden = false;
      initRichTextEditor(form);
      renderQuotePreview(form, quote);
      findEditorSurface(form)?.focus();
    }
    return;
  }

  if (action === 'toggle-replies') {
    const expanded = actionBtn.dataset.expanded === '1';
    if (expanded) {
      collapseReplies(postEl);
    } else {
      await loadReplies(postEl, 1);
    }
    return;
  }

  if (action === 'reply-to') {
    if (!currentUser) {
      location.href = authApi.startUrl();
      return;
    }
    if (topicState.isClosed) {
      return;
    }
    if (postEl.dataset.isRoot !== '1') {
      return;
    }
    const form = postEl.querySelector('[data-reply-form]');
    if (form) {
      form.hidden = false;
      initRichTextEditor(form);
      findEditorSurface(form)?.focus();
    }
    return;
  }

  if (action === 'cancel-reply') {
    const form = postEl.querySelector('[data-reply-form]');
    if (form) {
      form.hidden = true;
      clearEditor(findEditorSurface(form));
      hideRichToolbar();
      renderQuotePreview(form, null);
      showError(form, '');
    }
    return;
  }

  if (action === 'submit-reply') {
    const form = postEl.querySelector('[data-reply-form]');
    const body = readRichBody(form);
    if (!body) {
      showError(form, 'Введите текст ответа');
      return;
    }
    const quotedPostId = form?.dataset.quotedPostId
      ? Number(form.dataset.quotedPostId)
      : null;
    actionBtn.disabled = true;
    try {
      await forumApi.createReply(
        Number(postEl.dataset.postId),
        body,
        quotedPostId,
      );
      clearEditor(findEditorSurface(form));
      hideRichToolbar();
      renderQuotePreview(form, null);
      form.hidden = true;
      const count = Number(postEl.dataset.repliesCount || 0) + 1;
      postEl.dataset.repliesCount = String(count);
      let toggle = postEl.querySelector(
        '[data-action="toggle-replies"]',
      );
      if (!toggle) {
        const actions = postEl.querySelector('.post__actions');
        toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'quote-button replies-toggle';
        toggle.dataset.action = 'toggle-replies';
        actions?.appendChild(toggle);
      }
      await loadReplies(postEl, 1);
    } catch (error) {
      showError(form, error.message);
    } finally {
      actionBtn.disabled = false;
    }
    return;
  }

  if (action === 'edit-post') {
    const form = postEl.querySelector('[data-edit-form]');
    if (form) {
      form.hidden = false;
      const quotedId = postEl.dataset.quotedId
        ? Number(postEl.dataset.quotedId)
        : null;
      if (quotedId) {
        const quotedEl = document.getElementById(
          `post-${quotedId}`,
        );
        renderQuotePreview(
          form,
          quotedEl
            ? quoteFromPostEl(quotedEl)
            : {
                id: quotedId,
                author: 'Участник',
                bodySnippet: 'Цитата',
              },
        );
      } else {
        renderQuotePreview(form, null);
      }
      initRichTextEditor(form);
      findEditorSurface(form)?.focus();
    }
    return;
  }

  if (action === 'cancel-edit') {
    const form = postEl.querySelector('[data-edit-form]');
    if (form) {
      form.hidden = true;
      hideRichToolbar();
      renderQuotePreview(form, null);
      showError(form, '');
    }
    return;
  }

  if (action === 'submit-edit') {
    const form = postEl.querySelector('[data-edit-form]');
    const body = readRichBody(form);
    if (!body) {
      showError(form, 'Текст не может быть пустым');
      return;
    }
    const quotedPostId = form?.dataset.quotedPostId
      ? Number(form.dataset.quotedPostId)
      : null;
    actionBtn.disabled = true;
    try {
      const updated = await forumApi.updatePost(
        Number(postEl.dataset.postId),
        body,
        quotedPostId,
      );
      const textNode = postEl.querySelector('[data-post-text]');
      if (textNode) {
        textNode.innerHTML = renderFormattedBody(
          updated.body,
        );
      }
      renderQuotedBlock(postEl, updated.quotedPost);
      form.hidden = true;
      hideRichToolbar();
      renderQuotePreview(form, null);
      if (!updated.canEdit) {
        postEl
          .querySelector('[data-action="edit-post"]')
          ?.remove();
      }
    } catch (error) {
      showError(form, error.message);
    } finally {
      actionBtn.disabled = false;
    }
  }
}

function setNewTopicFormVisible(visible) {
  const form = document.querySelector('[data-new-topic-form]');
  if (!form) {
    return;
  }
  form.classList.toggle('is-open', visible);
  if (visible) {
    initRichTextEditor(form);
    form.querySelector('[name="title"]')?.focus();
  } else {
    form.reset();
    clearEditor(findEditorSurface(form));
    hideRichToolbar();
    showError(form, '');
    const aclBox = form.querySelector('[data-new-topic-acl]');
    if (aclBox) {
      aclBox.hidden = true;
    }
    const members = form.querySelector(
      '[data-new-topic-members]',
    );
    if (members) {
      members.innerHTML = '';
    }
    const results = form.querySelector(
      '[data-new-topic-results]',
    );
    if (results) {
      results.hidden = true;
      results.innerHTML = '';
    }
  }
}

function setNewCategoryFormVisible(form, visible) {
  if (!form) {
    return;
  }
  form.classList.toggle('is-open', visible);
  if (visible) {
    initRichTextEditor(form);
    form.querySelector('[name="title"]')?.focus();
    return;
  }
  form.reset();
  clearEditor(findEditorSurface(form));
  hideRichToolbar();
  showError(form, '');
  const aclBox = form.querySelector('[data-new-category-acl]');
  if (aclBox) {
    aclBox.hidden = true;
  }
  const members = form.querySelector(
    '[data-new-category-members]',
  );
  if (members) {
    members.innerHTML = '';
  }
  const results = form.querySelector(
    '[data-new-category-results]',
  );
  if (results) {
    results.hidden = true;
    results.innerHTML = '';
  }
}

function findDraftAclForm(node) {
  return (
    node?.closest('[data-new-topic-form]')
    || node?.closest('[data-new-category-form]')
    || null
  );
}

function draftAclHosts(form) {
  if (!form) {
    return {};
  }
  if (form.matches('[data-new-category-form]')) {
    return {
      members: form.querySelector(
        '[data-new-category-members]',
      ),
      results: form.querySelector(
        '[data-new-category-results]',
      ),
      search: form.querySelector(
        '[data-new-category-search]',
      ),
    };
  }
  return {
    members: form.querySelector('[data-new-topic-members]'),
    results: form.querySelector('[data-new-topic-results]'),
    search: form.querySelector('[data-new-topic-search]'),
  };
}

function getDraftMemberUids(container) {
  return [...container.querySelectorAll('[data-member-uid]')]
    .map((node) => node.dataset.memberUid)
    .filter(Boolean);
}

function renderMemberChips(container, members) {
  if (!container) {
    return;
  }
  if (!members.length) {
    container.innerHTML = `<li class="acl-panel__empty" data-acl-empty>
      Пока никого нет — выберите пользователей выше
    </li>`;
    return;
  }
  container.innerHTML = members
    .map(
      (member) => `<li
        class="acl-chip"
        data-member-uid="${member.uid}"
      >
        <span>${escapeText(
          member.displayName || member.username,
        )}</span>
        <button
          type="button"
          class="acl-chip__remove"
          data-action="acl-remove-member"
          data-uid="${member.uid}"
          aria-label="Удалить"
        >×</button>
      </li>`,
    )
    .join('');
}

function escapeText(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function showAclError(panel, message) {
  const node = panel?.querySelector('[data-acl-error]');
  if (!node) {
    return;
  }
  node.hidden = !message;
  node.textContent = message || '';
}

async function loadAclPanel(panel) {
  if (!panel) {
    return;
  }
  const entity = panel.dataset.aclEntity;
  const id = Number(panel.dataset.aclId);
  const membersHost = panel.querySelector('[data-acl-members]');
  const resultsHost = panel.querySelector('[data-acl-results]');
  const searchInput = panel.querySelector('[data-acl-search]');
  showAclError(panel, '');
  try {
    const members =
      entity === 'category'
        ? await forumApi.getCategoryMembers(id)
        : await forumApi.getTopicMembers(id);
    renderMemberChips(membersHost, members);
    if (resultsHost && searchInput) {
      await runAclSearch(searchInput, resultsHost, membersHost);
    }
  } catch (error) {
    showAclError(panel, error.message);
  }
}

async function saveAclMembers(panel) {
  const entity = panel.dataset.aclEntity;
  const id = Number(panel.dataset.aclId);
  const uids = getDraftMemberUids(
    panel.querySelector('[data-acl-members]'),
  );
  if (entity === 'category') {
    return forumApi.setCategoryMembers(id, uids);
  }
  return forumApi.setTopicMembers(id, uids);
}

let aclSearchTimer = null;

async function runAclSearch(input, resultsHost, selectedHost) {
  const query = input.value.trim();
  try {
    const users = await forumApi.searchUsers(query, 30);
    const selected = new Set(getDraftMemberUids(selectedHost));
    const filtered = users.filter(
      (user) => !selected.has(String(user.uid)),
    );
    if (!filtered.length) {
      resultsHost.hidden = false;
      resultsHost.innerHTML = query
        ? '<p class="acl-panel__empty">Никого не найдено</p>'
        : '<p class="acl-panel__empty">Нет доступных пользователей</p>';
      return;
    }
    resultsHost.hidden = false;
    resultsHost.innerHTML = filtered
      .map(
        (user) => `<button
          type="button"
          class="acl-result"
          data-action="acl-pick-user"
          data-uid="${user.uid}"
          data-name="${escapeText(
            user.displayName || user.username,
          )}"
        >${escapeText(
          user.displayName || user.username,
        )} <small>@${escapeText(user.username)}</small></button>`,
      )
      .join('');
  } catch (error) {
    resultsHost.hidden = false;
    resultsHost.innerHTML =
      `<p class="compose__error">${escapeText(error.message)}</p>`;
  }
}

async function handleForumClick(event) {
  const forumPage = event.target.closest('[data-forum-page]');
  const actionBtn = event.target.closest('[data-action]');
  if (!actionBtn) {
    return;
  }
  const action = actionBtn.dataset.action;

  if (action === 'open-new-topic') {
    if (!forumPage) {
      return;
    }
    if (!currentUser) {
      location.href = authApi.startUrl(
        location.hash || '#/',
      );
      return;
    }
    setNewTopicFormVisible(true);
    return;
  }
  if (action === 'cancel-new-topic') {
    setNewTopicFormVisible(false);
    return;
  }
  if (action === 'open-new-category') {
    if (!currentUser?.is_admin) {
      return;
    }
    const section = actionBtn.closest('[data-section-block]');
    const form = section?.querySelector(
      '[data-new-category-form]',
    );
    setNewCategoryFormVisible(form, true);
    return;
  }
  if (action === 'cancel-new-category') {
    const form = actionBtn.closest('[data-new-category-form]');
    setNewCategoryFormVisible(form, false);
    return;
  }
  if (action === 'toggle-category-visibility' && forumPage) {
    const categoryId = Number(forumPage.dataset.categoryId);
    const currentlyRestricted =
      actionBtn.dataset.restricted === '1';
    actionBtn.disabled = true;
    try {
      await forumApi.setCategoryVisibility(
        categoryId,
        !currentlyRestricted,
      );
      await render();
    } catch (error) {
      window.alert(error.message);
    } finally {
      actionBtn.disabled = false;
    }
    return;
  }
  if (action === 'acl-remove-member') {
    const panel = actionBtn.closest('[data-acl-panel]');
    const form = findDraftAclForm(actionBtn);
    const draft = draftAclHosts(form);
    const host =
      panel?.querySelector('[data-acl-members]')
      || draft.members;
    if (!host) {
      return;
    }
    actionBtn.closest('[data-member-uid]')?.remove();
    if (!getDraftMemberUids(host).length) {
      renderMemberChips(host, []);
    }
    const resultsHost =
      panel?.querySelector('[data-acl-results]')
      || draft.results;
    const searchInput =
      panel?.querySelector('[data-acl-search]')
      || draft.search;
    if (resultsHost && searchInput) {
      await runAclSearch(searchInput, resultsHost, host);
    }
    if (panel) {
      try {
        await saveAclMembers(panel);
      } catch (error) {
        showAclError(panel, error.message);
        await loadAclPanel(panel);
      }
    }
    return;
  }
  if (action === 'acl-pick-user') {
    const panel = actionBtn.closest('[data-acl-panel]');
    const form = findDraftAclForm(actionBtn);
    const draft = draftAclHosts(form);
    const membersHost =
      panel?.querySelector('[data-acl-members]')
      || draft.members;
    const resultsHost =
      panel?.querySelector('[data-acl-results]')
      || draft.results;
    const searchInput =
      panel?.querySelector('[data-acl-search]')
      || draft.search;
    if (!membersHost) {
      return;
    }
    const uid = actionBtn.dataset.uid;
    if (getDraftMemberUids(membersHost).includes(uid)) {
      return;
    }
    const chip = document.createElement('li');
    chip.className = 'acl-chip';
    chip.dataset.memberUid = uid;
    chip.innerHTML = `<span>${actionBtn.dataset.name || uid}</span>
      <button
        type="button"
        class="acl-chip__remove"
        data-action="acl-remove-member"
        data-uid="${uid}"
        aria-label="Удалить"
      >×</button>`;
    membersHost.querySelector('[data-acl-empty]')?.remove();
    membersHost.appendChild(chip);
    if (resultsHost && searchInput) {
      await runAclSearch(
        searchInput,
        resultsHost,
        membersHost,
      );
    }
    if (panel) {
      try {
        await saveAclMembers(panel);
      } catch (error) {
        showAclError(panel, error.message);
        await loadAclPanel(panel);
      }
    }
  }
}

async function handleForumSubmit(event) {
  const form = event.target.closest('[data-new-topic-form]');
  if (!form) {
    return;
  }
  event.preventDefault();
  if (!currentUser) {
    location.href = authApi.startUrl(
      location.hash || '#/',
    );
    return;
  }
  const categoryId = Number(form.dataset.categoryId);
  const title =
    form.querySelector('[name="title"]')?.value?.trim()
    || '';
  const body = readRichBody(form);
  if (!title) {
    showError(form, 'Введите название темы');
    return;
  }
  if (!body) {
    showError(form, 'Введите текст сообщения');
    return;
  }
  const isRestricted = Boolean(
    form.querySelector('[name="is_restricted"]')?.checked,
  );
  const allowedUserUids = getDraftMemberUids(
    form.querySelector('[data-new-topic-members]')
      || form,
  );
  const submitBtn = form.querySelector(
    'button[type="submit"]',
  );
  if (submitBtn) {
    submitBtn.disabled = true;
  }
  try {
    const created = await forumApi.createTopic(categoryId, {
      title,
      body,
      isRestricted,
      allowedUserUids,
    });
    location.hash = `#/topic/${created.id}`;
  } catch (error) {
    showError(form, error.message);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
    }
  }
}

async function handleNewCategorySubmit(event) {
  const form = event.target.closest(
    '[data-new-category-form]',
  );
  if (!form) {
    return;
  }
  event.preventDefault();
  if (!currentUser?.is_admin) {
    return;
  }
  const sectionId = Number(form.dataset.sectionId);
  const title =
    form.querySelector('[name="title"]')?.value?.trim()
    || '';
  const description = readRichBody(form);
  if (!title) {
    showError(form, 'Введите название категории');
    return;
  }
  const isRestricted = Boolean(
    form.querySelector('[name="is_restricted"]')?.checked,
  );
  const allowedUserUids = getDraftMemberUids(
    form.querySelector('[data-new-category-members]')
      || form,
  );
  const submitBtn = form.querySelector(
    'button[type="submit"]',
  );
  if (submitBtn) {
    submitBtn.disabled = true;
  }
  try {
    const created = await forumApi.createCategory(
      sectionId,
      {
        title,
        description: description || undefined,
        isRestricted,
        allowedUserUids,
      },
    );
    location.hash = `#/forum/${created.id}`;
  } catch (error) {
    showError(form, error.message);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
    }
  }
}

async function handleTopicSubmit(event) {
  const form = event.target.closest('[data-compose-root]');
  if (!form || !topicState) {
    return;
  }
  event.preventDefault();
  if (!currentUser) {
    location.href = authApi.startUrl();
    return;
  }
  const body = readRichBody(form);
  if (!body) {
    showError(form, 'Введите текст сообщения');
    return;
  }
  const quotedPostId = form.dataset.quotedPostId
    ? Number(form.dataset.quotedPostId)
    : null;
  const submitBtn = form.querySelector('button[type="submit"]');
  if (submitBtn) {
    submitBtn.disabled = true;
  }
  try {
    await forumApi.createTopicPost(
      topicState.id,
      body,
      quotedPostId,
    );
    clearEditor(findEditorSurface(form));
    hideRichToolbar();
    renderQuotePreview(form, null);
    showError(form, '');
    setComposeVisible(false);
    await changeRootsPage(1);
  } catch (error) {
    showError(form, error.message);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
    }
  }
}

function showProfileMessage(container, { error = '', success = '' } = {}) {
  const errorNode = container?.querySelector('[data-error]');
  const successNode = container?.querySelector('[data-success]');
  if (errorNode) {
    errorNode.hidden = !error;
    errorNode.textContent = error || '';
  }
  if (successNode) {
    successNode.hidden = !success;
    successNode.textContent = success || '';
  }
}

async function handleProfileClick(event) {
  const actionBtn = event.target.closest('[data-action]');
  if (!actionBtn) {
    return;
  }

  const action = actionBtn.dataset.action;
  const form = document.querySelector('[data-profile-form]');

  if (action === 'change-password') {
    event.preventDefault();
    try {
      const payload = await authApi.getChangePasswordUrl();
      location.href = payload.url;
    } catch (error) {
      showProfileMessage(form, {
        error: error.message || 'Не удалось открыть Keycloak',
      });
    }
    return;
  }

  if (action === 'clear-avatar' && form) {
    actionBtn.disabled = true;
    showProfileMessage(form, { error: '', success: '' });
    try {
      const profile = await authApi.deleteProfileAvatar();
      currentUser = {
        ...profile,
        is_admin: Boolean(currentUser?.is_admin),
      };
      updateHeaderAuth();
      app.innerHTML = profileTemplate(profile);
      showProfileMessage(
        app.querySelector('[data-profile-form]'),
        { success: 'Фото удалено' },
      );
    } catch (error) {
      showProfileMessage(form, {
        error: error.message || 'Не удалось удалить фото',
      });
      actionBtn.disabled = false;
    }
  }
}

async function handleProfileSubmit(event) {
  const form = event.target.closest('[data-profile-form]');
  if (!form) {
    return;
  }
  event.preventDefault();
  const nameInput = form.querySelector('[name="display_name"]');
  const fileInput = form.querySelector('[name="avatar_file"]');
  const displayName = nameInput?.value?.trim() || '';
  if (!displayName) {
    showProfileMessage(form, {
      error: 'Введите никнейм',
    });
    return;
  }
  const submitBtn = form.querySelector('button[type="submit"]');
  if (submitBtn) {
    submitBtn.disabled = true;
  }
  showProfileMessage(form, { error: '', success: '' });
  try {
    let profile = await authApi.updateProfile(displayName);
    const file = fileInput?.files?.[0];
    if (file) {
      profile = await authApi.uploadProfileAvatar(file);
    }
    currentUser = {
      ...profile,
      is_admin: Boolean(currentUser?.is_admin),
    };
    updateHeaderAuth();
    app.innerHTML = profileTemplate(profile);
    showProfileMessage(
      app.querySelector('[data-profile-form]'),
      { success: 'Профиль сохранён' },
    );
  } catch (error) {
    showProfileMessage(form, {
      error: error.message || 'Не удалось сохранить профиль',
    });
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
    }
  }
}

function showSupportMessage(form, { error = '', success = '' }) {
  const errorNode = form?.querySelector('[data-error]');
  const successNode = form?.querySelector('[data-success]');
  if (errorNode) {
    errorNode.hidden = !error;
    errorNode.textContent = error || '';
  }
  if (successNode) {
    successNode.hidden = !success;
    successNode.textContent = success || '';
  }
}

async function handleSupportSubmit(event) {
  const form = event.target.closest('[data-support-form]');
  if (!form) {
    return;
  }
  event.preventDefault();

  const subjectInput = form.querySelector('[name="subject"]');
  const emailInput = form.querySelector('[name="email"]');
  const bodyInput = form.querySelector('[name="body"]');
  const subject = subjectInput?.value?.trim() || '';
  const body = bodyInput?.value?.trim() || '';
  const email = currentUser?.email
    || emailInput?.value?.trim()
    || '';

  showSupportMessage(form, { error: '', success: '' });

  if (!subject) {
    showSupportMessage(form, { error: 'Укажите тему' });
    return;
  }
  if (!body) {
    showSupportMessage(form, { error: 'Введите сообщение' });
    return;
  }
  if (currentUser && !currentUser.email) {
    showSupportMessage(form, {
      error: 'В профиле не указан email',
    });
    return;
  }
  if (!currentUser && !email) {
    showSupportMessage(form, { error: 'Укажите email' });
    return;
  }

  const submitBtn = form.querySelector('button[type="submit"]');
  if (submitBtn) {
    submitBtn.disabled = true;
  }
  try {
    const result = await forumApi.submitSupportTicket({
      subject,
      body,
      email: currentUser ? currentUser.email : email,
    });
    form.reset();
    if (currentUser?.email && emailInput) {
      emailInput.value = currentUser.email;
    }
    showSupportMessage(form, {
      success: result.message || 'Обращение отправлено',
    });
  } catch (error) {
    const message = error.status === 429
      ? (error.message
        || 'Достигнут лимит: не более 2 обращений в сутки')
      : (error.message || 'Не удалось отправить обращение');
    showSupportMessage(form, { error: message });
  } finally {
    if (submitBtn && !(currentUser && !currentUser.email)) {
      submitBtn.disabled = false;
    }
  }
}

function stopChatReadObserver() {
  if (chatReadObserver) {
    chatReadObserver.disconnect();
    chatReadObserver = null;
  }
  if (chatReadFlushTimer) {
    clearTimeout(chatReadFlushTimer);
    chatReadFlushTimer = null;
  }
  chatReadPending = new Set();
}

function setChatRowBadge(chatId, count) {
  const row = document.querySelector(
    `[data-chats-list] [data-chat-id="${chatId}"]`,
  );
  if (!row) {
    return;
  }
  setBadge(
    row.querySelector('[data-chat-row-badge]'),
    count,
  );
}

async function flushVisibleChatReads() {
  if (!currentUser || !chatReadPending.size) {
    return;
  }
  const ids = Array.from(chatReadPending);
  chatReadPending = new Set();
  try {
    const result =
      await notificationsApi.markChatMessagesVisible(ids);
    notificationsState.chatUnreadCount = result.unreadCount;
    updateHeaderBadges();
    const marked = new Set(result.markedIds || []);
    if (chatState?.messages) {
      chatState.messages = chatState.messages.map((message) => {
        if (!marked.has(message.id)) {
          return message;
        }
        return {
          ...message,
          readAt: message.readAt || new Date().toISOString(),
        };
      });
    }
    if (chatState?.chats && chatState.chatId != null) {
      const markedCount = marked.size;
      chatState.chats = chatState.chats.map((chat) => {
        if (Number(chat.id) !== Number(chatState.chatId)) {
          return chat;
        }
        return {
          ...chat,
          unreadCount: Math.max(
            0,
            (Number(chat.unreadCount) || 0) - markedCount,
          ),
        };
      });
      const active = chatState.chats.find(
        (chat) =>
          Number(chat.id) === Number(chatState.chatId),
      );
      setChatRowBadge(
        chatState.chatId,
        active?.unreadCount || 0,
      );
    }
    document
      .querySelectorAll('[data-chat-unread="1"]')
      .forEach((node) => {
        const id = Number(node.dataset.messageId);
        if (ids.includes(id)) {
          node.removeAttribute('data-chat-unread');
        }
      });
  } catch (error) {
    console.error(error);
  }
}

function scheduleVisibleChatReads(messageId) {
  chatReadPending.add(Number(messageId));
  if (chatReadFlushTimer) {
    clearTimeout(chatReadFlushTimer);
  }
  chatReadFlushTimer = setTimeout(() => {
    void flushVisibleChatReads();
  }, 400);
}

function setupChatReadObserver() {
  stopChatReadObserver();
  const container = document.querySelector(
    '[data-chat-messages]',
  );
  if (!container || !currentUser) {
    return;
  }
  chatReadObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }
        const node = entry.target;
        if (node.dataset.chatUnread !== '1') {
          return;
        }
        const messageId = Number(node.dataset.messageId);
        if (!messageId) {
          return;
        }
        scheduleVisibleChatReads(messageId);
      });
    },
    {
      root: container,
      threshold: 0.6,
    },
  );
  container
    .querySelectorAll('[data-chat-unread="1"]')
    .forEach((node) => chatReadObserver.observe(node));
}

function bindChatBubbleNode(node, message) {
  if (!node || !message) {
    return;
  }
  node.dataset.messageId = String(message.id);
  if (!message.isMine && !message.readAt) {
    node.dataset.chatUnread = '1';
  } else {
    node.removeAttribute('data-chat-unread');
  }
  const text = node.querySelector('.chat-bubble__text');
  const time = node.querySelector('.chat-bubble__time');
  if (text) {
    text.innerHTML = renderFormattedBody(message.body);
  }
  if (time) {
    time.textContent = message.time || '';
  }
}

async function loadChatsPage(activeChatId = null) {
  stopChatReadObserver();
  const chats = await chatsApi.getMyChats();
  let peer = null;
  let messages = [];
  if (activeChatId) {
    const pageData = await chatsApi.getChatMessages(
      activeChatId,
    );
    peer = pageData.peer;
    messages = pageData.items;
    chatState = {
      chatId: Number(activeChatId),
      peer,
      messages,
      chats,
    };
    startChatPolling(activeChatId);
  } else {
    chatState = { chatId: null, peer: null, messages: [], chats };
  }
  return chatsPageTemplate({
    chats,
    activeChatId,
    peer,
    messages,
  });
}

async function refreshActiveChat(
  chatId,
  { silent = false } = {},
) {
  if (!chatState || Number(chatState.chatId) !== Number(chatId)) {
    return;
  }
  try {
    const [chats, pageData] = await Promise.all([
      chatsApi.getMyChats(),
      chatsApi.getChatMessages(chatId),
    ]);
    const container = document.querySelector(
      '[data-chat-messages]',
    );
    const list = document.querySelector('[data-chats-list]');
    if (!container) {
      return;
    }
    const prevIds = (chatState.messages || [])
      .map((item) => item.id)
      .join(',');
    const nextIds = pageData.items
      .map((item) => item.id)
      .join(',');
    chatState.messages = pageData.items;
    chatState.peer = pageData.peer;
    chatState.chats = chats;
    if (prevIds !== nextIds) {
      const nearBottom =
        container.scrollHeight - container.scrollTop
        - container.clientHeight < 80;
      container.innerHTML = pageData.items.length
        ? pageData.items
            .map((message) => {
              const mine = message.isMine
                ? ' chat-bubble--own'
                : '';
              return `<div class="chat-bubble${mine}" data-message-id="${message.id}">
                <div class="chat-bubble__text"></div>
                <time class="chat-bubble__time"></time>
              </div>`;
            })
            .join('')
        : '<p class="chats-empty">Напишите первое сообщение</p>';
      container
        .querySelectorAll('[data-message-id]')
        .forEach((node, index) => {
          bindChatBubbleNode(node, pageData.items[index]);
        });
      if (nearBottom || !silent) {
        container.scrollTop = container.scrollHeight;
      }
      setupChatReadObserver();
    }
    if (list) {
      list.innerHTML = chats.length
        ? chats
            .map((chat) =>
              chatListItemTemplate(chat, {
                activeId: chatId,
              }),
            )
            .join('')
        : '<p class="chats-empty">Пока нет диалогов.</p>';
    }
  } catch (error) {
    if (!silent) {
      console.error(error);
    }
  }
}

async function openDirectChat(userUid) {
  const chat = await chatsApi.getOrCreateDirectChat(userUid);
  location.hash = `#/chats/${chat.id}`;
}

async function handleChatSubmit(event) {
  const form = event.target.closest('[data-chat-composer]');
  if (!form) {
    return;
  }
  event.preventDefault();
  if (!currentUser) {
    location.href = authApi.startUrl('#/chats');
    return;
  }
  const chatId = Number(form.dataset.chatId);
  const body = readRichBody(form);
  if (!body) {
    showError(form, 'Введите сообщение');
    return;
  }
  const submitBtn = form.querySelector('button[type="submit"]');
  if (submitBtn) {
    submitBtn.disabled = true;
  }
  try {
    await chatsApi.sendMessage(chatId, body);
    clearEditor(findEditorSurface(form));
    hideRichToolbar();
    showError(form, '');
    await refreshActiveChat(chatId);
    const container = document.querySelector(
      '[data-chat-messages]',
    );
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  } catch (error) {
    showError(form, error.message);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
    }
  }
}

async function render() {
  const path = currentPath();
  const query = currentQuery();
  topicState = null;
  stopChatPolling();
  stopChatReadObserver();
  chatState = null;

  if (path === '/login') {
    location.replace(
      authApi.startUrl(location.hash || '#/'),
    );
    return;
  }

  if (path === '/profile' && !currentUser) {
    location.href = authApi.startUrl('#/profile');
    return;
  }

  if (path === '/participated' && !currentUser) {
    location.href = authApi.startUrl('#/participated');
    return;
  }

  if (
    (path === '/chats' || path.startsWith('/chats/'))
    && !currentUser
  ) {
    location.href = authApi.startUrl(location.hash || '#/chats');
    return;
  }

  app.classList.add('is-loading');
  app.innerHTML =
    '<div class="page-loader"><i></i><span>Загружаем…</span></div>';
  try {
    const topicMatch = path.match(/^\/topic\/(\d+)$/);
    const forumMatch = path.match(/^\/forum\/(\d+)$/);
    const sectionMatch = path.match(/^\/section\/(\d+)$/);
    const userMatch = path.match(
      /^\/users\/([0-9a-fA-F-]{36})$/,
    );
    const chatNewMatch = path.match(
      /^\/chats\/new\/([0-9a-fA-F-]{36})$/,
    );
    const chatMatch = path.match(/^\/chats\/(\d+)$/);
    let page;
    if (chatNewMatch) {
      await openDirectChat(chatNewMatch[1]);
      return;
    }
    if (path === '/chats') {
      page = await loadChatsPage();
    } else if (chatMatch) {
      page = await loadChatsPage(chatMatch[1]);
    } else if (topicMatch) {
      const pageFromQuery = Number(query.get('page') || 1);
      page = await loadTopicPage(
        topicMatch[1],
        pageFromQuery > 0 ? pageFromQuery : 1,
      );
      const postFromQuery = Number(query.get('post') || 0);
      if (postFromQuery) {
        pendingPostJump = {
          postId: postFromQuery,
          parentPostId: Number(query.get('parent') || 0) || null,
          repliesPage: Number(query.get('rpage') || 1) || 1,
        };
      }
    } else if (forumMatch) {
      page = forumTemplate(
        await forumApi.getForum(forumMatch[1]),
        {
          isAuthenticated: Boolean(currentUser),
          isAdmin: Boolean(currentUser?.is_admin),
        },
      );
    } else if (sectionMatch) {
      page = sectionTemplate(
        await forumApi.getSection(sectionMatch[1]),
        { isAdmin: Boolean(currentUser?.is_admin) },
      );
    } else if (userMatch) {
      const profile = await forumApi.getUserProfile(
        userMatch[1],
      );
      page = publicProfileTemplate(profile, {
        isAuthenticated: Boolean(currentUser),
        isSelf: Boolean(
          currentUser
          && String(currentUser.uid) === String(profile.uid),
        ),
      });
    } else if (routes[path]) {
      page = await routes[path]();
    } else {
      page = notFoundTemplate;
    }
    app.innerHTML = page;
    initRichTextEditor(app);
    if (chatMatch) {
      const container = document.querySelector(
        '[data-chat-messages]',
      );
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
      setupChatReadObserver();
    }
    const aclPanel = document.querySelector('[data-acl-panel]');
    if (aclPanel) {
      await loadAclPanel(aclPanel);
    }
  } catch (error) {
    console.error(error);
    const message =
      error.message ||
      'Проверьте, что API запущен и CORS настроен.';
    app.innerHTML = `
      <section class="empty-state">
        <span>◌</span>
        <h1>Не удалось загрузить данные</h1>
        <p>${message}</p>
        <a class="button" href="#/">На главную</a>
      </section>
    `;
  } finally {
    app.classList.remove('is-loading');
    updateHeaderAuth();
    if (currentUser) {
      void refreshNotifications();
    }
    const jump = pendingPostJump;
    pendingPostJump = null;
    if (jump) {
      setTimeout(() => {
        void focusPostFromJump(jump);
      }, 50);
    } else {
      const position = historyNavigation
        ? scrollPositions.get(path)
        : 0;
      historyNavigation = false;
      window.scrollTo({
        top: position || 0,
        behavior: position ? 'auto' : 'smooth',
      });
    }
  }
}

document
  .querySelector('.search-toggle')
  .addEventListener('click', () => {
    const panel = document.querySelector('.search-panel');
    panel.hidden = !panel.hidden;
    if (!panel.hidden) {
      setNotifyPanelOpen(false);
      document.querySelector('#search-input').focus();
    }
  });

const notifyToggle = document.querySelector(
  '[data-notify-toggle]',
);
if (notifyToggle) {
  notifyToggle.addEventListener('click', (event) => {
    event.stopPropagation();
    const panel = document.querySelector('[data-notify-panel]');
    const willOpen = Boolean(panel?.hidden);
    if (willOpen) {
      const searchPanel = document.querySelector(
        '.search-panel',
      );
      if (searchPanel) {
        searchPanel.hidden = true;
      }
      void refreshNotifications();
    }
    setNotifyPanelOpen(willOpen);
  });
}

const notifyPanel = document.querySelector(
  '[data-notify-panel]',
);
if (notifyPanel) {
  notifyPanel.addEventListener('click', async (event) => {
    const actionBtn = event.target.closest('[data-action]');
    if (!actionBtn) {
      return;
    }
    const action = actionBtn.dataset.action;
    const notifyId = Number(actionBtn.dataset.notifyId);
    if (action === 'open-notification') {
      event.preventDefault();
      const item = (notificationsState.items || []).find(
        (entry) => entry.id === notifyId,
      );
      await openNotification(item);
      return;
    }
    if (action === 'dismiss-notification') {
      event.preventDefault();
      event.stopPropagation();
      try {
        await notificationsApi.dismiss(notifyId);
        notificationsState.items = (
          notificationsState.items || []
        ).filter((entry) => entry.id !== notifyId);
        notificationsState.unreadCount = Math.max(
          0,
          (notificationsState.unreadCount || 0) - 1,
        );
        updateHeaderBadges();
        renderNotifyList();
      } catch (error) {
        console.error(error);
      }
      return;
    }
    if (action === 'clear-notifications') {
      event.preventDefault();
      try {
        await notificationsApi.clearAll();
        notificationsState.items = [];
        notificationsState.unreadCount = 0;
        updateHeaderBadges();
        renderNotifyList();
      } catch (error) {
        console.error(error);
      }
    }
  });
}

document
  .querySelector('.menu-button')
  .addEventListener('click', (event) => {
    event.currentTarget.classList.toggle('is-open');
    event.currentTarget.setAttribute(
      'aria-expanded',
      event.currentTarget.classList.contains('is-open'),
    );
    document
      .querySelector('.main-nav')
      .classList.toggle('is-open');
  });

document.addEventListener('click', (event) => {
  const link = event.target.closest('a[href^="#/"]');
  if (link) {
    scrollPositions.set(currentPath(), window.scrollY);
  }
  const notifyRoot = document.querySelector('.header-notify');
  if (
    notifyRoot
    && !notifyRoot.contains(event.target)
  ) {
    setNotifyPanelOpen(false);
  }
});

app.addEventListener('click', (event) => {
  void handleTopicClick(event);
  void handleForumClick(event);
});

app.addEventListener('input', (event) => {
  const restrictedToggle = event.target.closest(
    '[data-new-topic-restricted], [data-new-category-restricted]',
  );
  if (restrictedToggle) {
    const form = findDraftAclForm(restrictedToggle);
    const draft = draftAclHosts(form);
    const aclBox =
      form?.querySelector('[data-new-topic-acl]')
      || form?.querySelector('[data-new-category-acl]');
    if (aclBox) {
      aclBox.hidden = !restrictedToggle.checked;
      if (
        restrictedToggle.checked
        && draft.search
        && draft.results
        && draft.members
      ) {
        void runAclSearch(
          draft.search,
          draft.results,
          draft.members,
        );
      }
    }
    return;
  }

  const aclSearch = event.target.closest('[data-acl-search]');
  const draftSearch = event.target.closest(
    '[data-new-topic-search], [data-new-category-search]',
  );
  const input = aclSearch || draftSearch;
  if (!input) {
    return;
  }
  const panel = input.closest('[data-acl-panel]');
  const form = findDraftAclForm(input);
  const draft = draftAclHosts(form);
  const resultsHost =
    panel?.querySelector('[data-acl-results]')
    || draft.results;
  const membersHost =
    panel?.querySelector('[data-acl-members]')
    || draft.members;
  if (!resultsHost || !membersHost) {
    return;
  }
  if (aclSearchTimer) {
    clearTimeout(aclSearchTimer);
  }
  aclSearchTimer = setTimeout(() => {
    void runAclSearch(input, resultsHost, membersHost);
  }, 250);
});

app.addEventListener('submit', (event) => {
  void handleTopicSubmit(event);
  void handleForumSubmit(event);
  void handleNewCategorySubmit(event);
  void handleProfileSubmit(event);
  void handleChatSubmit(event);
  void handleSupportSubmit(event);
});

app.addEventListener('click', (event) => {
  const loginAction = event.target.closest(
    '[data-action="login"]',
  );
  if (
    loginAction
    && event.target.closest('.profile-page')
  ) {
    event.preventDefault();
    location.href = authApi.startUrl(
      location.hash || '#/',
    );
  }
});

app.addEventListener('click', (event) => {
  void handleProfileClick(event);
});

if (headerLogoutButton) {
  headerLogoutButton.addEventListener('click', () => {
    location.href = authApi.logoutUrl();
  });
}

window.addEventListener('popstate', () => {
  historyNavigation = true;
});
window.addEventListener('hashchange', render);

void (async () => {
  await refreshSession();
  await render();
})();
