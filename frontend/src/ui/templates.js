import {
  renderFormattedBody,
  richEditorMarkup,
} from './rich-text.js';

const icon = '<span class="forum-icon" aria-hidden="true">◌</span>';
const format = (number) => new Intl.NumberFormat('ru-RU').format(number);
const LIST_DESCRIPTION_MAX_LENGTH = 235;

const escapeHtml = (value) =>
  String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

const truncateDescription = (value, maxLength = LIST_DESCRIPTION_MAX_LENGTH) => {
  const text = String(value ?? '').trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength).trimEnd()}...`;
};

const userProfileHref = (uid) =>
  uid ? `#/users/${escapeHtml(uid)}` : '';

const formatProfileDate = (value) => {
  if (!value) {
    return '—';
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
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Moscow',
  }).format(date);
};

function topicRow(item) {
  const href = item.isTopic
    ? `#/topic/${item.id}`
    : item.isCategory
      ? `#/forum/${item.id}`
      : `#/section/${item.id}`;
  const showStats = item.isTopic || item.isCategory;
  const lastPostHref = item.lastPost?.topicId
    ? `#/topic/${item.lastPost.topicId}`
    : href;
  const authorUid = item.lastPost?.authorUid;
  const authorName = escapeHtml(item.lastPost?.author || '—');
  const authorHtml = authorUid
    ? `<a class="user-link" href="${userProfileHref(authorUid)}">${authorName}</a>`
    : `<b>${authorName}</b>`;
  const description = truncateDescription(item.description || '');
  return `<article class="topic-row">
    <div class="topic-row__info">${icon}<div>
      <a class="topic-row__title" href="${href}">${escapeHtml(item.title)}</a>
      ${
        description
          ? `<p>${escapeHtml(description)}</p>`
          : ''
      }
    </div></div>
    ${
      showStats
        ? `<dl class="topic-row__stat"><dt>Темы</dt><dd>${format(item.topics)}</dd></dl>
    <dl class="topic-row__stat"><dt>Сообщения</dt><dd>${format(item.posts)}</dd></dl>
    <div class="last-post">
      <span>Последнее сообщение</span>
      <a href="${lastPostHref}">${escapeHtml(item.lastPost?.title || '—')}</a>
      <p>${escapeHtml(item.lastPost?.time || '')} · ${authorHtml}</p>
    </div>`
        : '<div class="topic-row__spacer"></div>'
    }
  </article>`;
}

function newCategoryFormMarkup(sectionId) {
  return `<form
      class="compose new-category-form"
      data-new-category-form
      data-section-id="${sectionId}"
    >
      <label class="compose__field">
        <span class="compose__label">Название категории</span>
        <input
          type="text"
          name="title"
          required
          maxlength="200"
          placeholder="Название категории"
        >
      </label>
      <div class="compose__field">
        <span class="compose__label">Описание</span>
        ${richEditorMarkup({
          name: 'description',
          placeholder: 'Краткое описание категории…',
          minRows: 3,
        })}
      </div>
      <label class="acl-toggle">
        <input
          type="checkbox"
          name="is_restricted"
          data-new-category-restricted
        >
        <span>Скрытая категория</span>
      </label>
      <div
        class="acl-create"
        data-new-category-acl
        hidden
      >
        <label>
          <span>Допустить пользователей</span>
          <input
            type="search"
            data-new-category-search
            placeholder="Начните вводить имя или выберите из списка…"
            autocomplete="off"
          >
        </label>
        <div
          class="acl-panel__results"
          data-new-category-results
        ></div>
        <p class="acl-panel__members-label">Добавлены:</p>
        <ul
          class="acl-panel__members"
          data-new-category-members
        ></ul>
      </div>
      <div class="compose__actions">
        <button class="button" type="submit">
          Создать категорию
        </button>
        <button
          class="button button--soft"
          type="button"
          data-action="cancel-new-category"
        >Отмена</button>
      </div>
      <p class="compose__error" data-error hidden></p>
    </form>`;
}

function sectionAdminToolsMarkup(sectionId) {
  return `<div class="section-admin-toolbar">
      <div class="section-admin-toolbar__spacer" aria-hidden="true"></div>
      <div class="section-admin-toolbar__spacer" aria-hidden="true"></div>
      <div class="section-admin-toolbar__spacer" aria-hidden="true"></div>
      <div class="section-admin-toolbar__action">
        <button
          type="button"
          class="button"
          data-action="open-new-category"
        >Новая категория</button>
      </div>
    </div>
    ${newCategoryFormMarkup(sectionId)}`;
}

function categorySectionBlock(section, { isAdmin = false } = {}) {
  const categories = (section.categories || []).map(
    (category) => ({
      ...category,
      isCategory: true,
      isTopic: false,
    }),
  );
  const adminTools = isAdmin
    ? sectionAdminToolsMarkup(section.id)
    : '';
  return `<section
    class="category-section ${section.isTopic ? 'category-section--featured' : ''}"
    data-section-block
    data-section-id="${section.id}"
  >
    <div class="category-heading">
      <h2><a href="#/section/${section.id}">${escapeHtml(section.title)}</a></h2>
      <span class="category-heading__topics">Темы</span>
      <span class="category-heading__posts">Сообщения</span>
      <span>Последнее сообщение</span>
    </div>
    ${adminTools}
    <div class="topic-table">${
      categories.length
        ? categories.map(topicRow).join('')
        : '<p class="replies__empty">В этом разделе пока нет категорий</p>'
    }</div>
  </section>`;
}

function sectionsGroup(title, sections, { isAdmin = false } = {}) {
  if (!sections.length) {
    return '';
  }
  return `<div class="categories-divider"><span>${escapeHtml(title)}</span></div>
    ${sections
      .map((section) => categorySectionBlock(section, { isAdmin }))
      .join('')}`;
}

export const paginationTemplate = (
  {
    page,
    totalPages,
    total,
    prefix = 'roots',
  },
) => {
  if (totalPages <= 1) {
    return '';
  }
  return `<nav class="pagination" data-pagination="${prefix}" aria-label="Пагинация">
    <button type="button" class="pagination__btn" data-page-action="prev" ${page <= 1 ? 'disabled' : ''}>←</button>
    <span class="pagination__meta">Стр. ${page} из ${totalPages} · ${format(total)}</span>
    <label class="pagination__jump">
      <span>На стр.</span>
      <input type="number" min="1" max="${totalPages}" value="${page}" data-page-input>
    </label>
    <button type="button" class="pagination__btn" data-page-action="go">Перейти</button>
    <button type="button" class="pagination__btn" data-page-action="next" ${page >= totalPages ? 'disabled' : ''}>→</button>
  </nav>`;
};

export const postCardTemplate = (post, { depth = 0 } = {}) => {
  const isRoot = depth === 0;
  const repliesLabel =
    post.repliesCount > 0
      ? `Ответы (${post.repliesCount})`
      : null;
  const profileHref = userProfileHref(post.authorUid);
  const quoteAuthor = escapeHtml(post.quotedPost?.author || '');
  const quoteAuthorHtml = post.quotedPost?.authorUid
    ? `<a class="post-quote__author user-link" href="${userProfileHref(post.quotedPost.authorUid)}">${quoteAuthor}</a>`
    : `<span class="post-quote__author">${quoteAuthor}</span>`;
  const quoteBlock = post.quotedPost
    ? `<div class="post-quote">
        ${quoteAuthorHtml}
        <a class="post-quote__text" href="${escapeHtml(post.quotedPost.jumpTarget)}" data-action="jump-quote" data-quote-id="${post.quotedPost.id}">${escapeHtml(post.quotedPost.bodySnippet)}</a>
      </div>`
    : '';
  const avatarInner = post.avatarUrl
    ? `<img class="avatar avatar--image" src="${escapeHtml(post.avatarUrl)}" alt="">`
    : `<span class="avatar">${escapeHtml(post.initials)}</span>`;
  const avatarHtml = profileHref
    ? `<a class="user-link user-link--avatar" href="${profileHref}" title="Профиль">${avatarInner}</a>`
    : avatarInner;
  const authorHtml = profileHref
    ? `<a class="user-link" href="${profileHref}"><b>${escapeHtml(post.author)}</b></a>`
    : `<b>${escapeHtml(post.author)}</b>`;
  return `<article class="post" id="post-${post.id}" data-post-id="${post.id}" data-depth="${depth}" data-is-root="${isRoot ? '1' : '0'}" data-replies-count="${post.repliesCount}" data-quoted-id="${post.quotedPost?.id || ''}" data-author-uid="${escapeHtml(post.authorUid || '')}">
    <aside>
      ${avatarHtml}
      ${authorHtml}
      <small>Участник</small>
    </aside>
    <div class="post__body">
      <div class="post__meta">
        <span>${escapeHtml(post.date)}</span>
        <a href="#post-${post.id}">#${post.id}</a>
      </div>
      ${quoteBlock}
      <div class="post__text" data-post-text>${renderFormattedBody(post.body)}</div>
      <div class="post__actions">
        ${
          isRoot
            ? '<button type="button" class="quote-button" data-action="reply-to">Ответить</button>'
            : ''
        }
        <button type="button" class="quote-button" data-action="quote-post">Цитировать</button>
        ${
          post.canEdit
            ? '<button type="button" class="quote-button" data-action="edit-post">Редактировать</button>'
            : ''
        }
        ${
          isRoot && repliesLabel
            ? `<button type="button" class="quote-button replies-toggle" data-action="toggle-replies">${repliesLabel}</button>`
            : ''
        }
      </div>
      ${
        isRoot
          ? `<div class="reply-form" data-reply-form hidden>
        <div class="quote-preview" data-quote-preview hidden></div>
        ${richEditorMarkup({
          name: 'body',
          placeholder: 'Ваш ответ…',
          minRows: 3,
        })}
        <div class="compose__actions">
          <button type="button" class="button" data-action="submit-reply">Отправить</button>
          <button type="button" class="button button--soft" data-action="cancel-reply">Отмена</button>
        </div>
        <p class="compose__error" data-error hidden></p>
      </div>`
          : ''
      }
      <div class="edit-form" data-edit-form hidden>
        <div class="quote-preview" data-quote-preview hidden></div>
        ${richEditorMarkup({
          name: 'body',
          placeholder: 'Редактировать сообщение…',
          initialHtml: post.body || '',
          minRows: 4,
        })}
        <div class="compose__actions">
          <button type="button" class="button" data-action="submit-edit">Сохранить</button>
          <button type="button" class="button button--soft" data-action="cancel-edit">Отмена</button>
        </div>
        <p class="compose__error" data-error hidden></p>
      </div>
      ${
        isRoot
          ? '<div class="replies" data-replies hidden></div>'
          : ''
      }
    </div>
  </article>`;
};

export const repliesBlockTemplate = (
  parentId,
  pageData,
  { depth = 1 } = {},
) => {
  const postsHtml = pageData.items
    .map((post) => postCardTemplate(post, { depth }))
    .join('');
  return `
    <div class="replies__toolbar replies__toolbar--top">
      <button type="button" class="button button--soft" data-action="collapse-replies" data-parent-id="${parentId}">Свернуть ответы</button>
      <span class="replies__count">${format(pageData.total)} ответов</span>
    </div>
    <div class="replies__list">${postsHtml || '<p class="replies__empty">Пока нет ответов</p>'}</div>
    ${paginationTemplate({
      page: pageData.page,
      totalPages: pageData.totalPages,
      total: pageData.total,
      prefix: `replies-${parentId}`,
    })}
    <div class="replies__toolbar replies__toolbar--bottom">
      <button type="button" class="button button--soft" data-action="collapse-replies" data-parent-id="${parentId}">Свернуть ответы</button>
    </div>
  `;
};

export const homeTemplate = (
  home,
  { isAuthenticated = false, isAdmin = false } = {},
) => {
  const sections = home.sections || home || [];
  const members = new Intl.NumberFormat('ru-RU').format(
    home.communityMembersCount ?? 0,
  );
  const todayActive = new Intl.NumberFormat('ru-RU').format(
    home.todayActiveMembersCount ?? 0,
  );
  const regular = sections
    .filter((section) => !section.isTopic)
    .sort((a, b) => (a.position || 99) - (b.position || 99));
  const special = sections
    .filter((section) => section.isTopic)
    .sort((a, b) => (a.position || 99) - (b.position || 99));
  const firstCategory = [...special, ...regular]
    .flatMap((section) => section.categories || [])
    .sort((a, b) => (a.position || 99) - (b.position || 99))[0];
  const discussionsHref = firstCategory
    ? `#/forum/${firstCategory.id}`
    : '#/active';
  const participatedLink = isAuthenticated
    ? '<a href="#/participated">◯ <span><b>С вашим участием</b><small>темы с вашими сообщениями</small></span><em>→</em></a>'
    : '';
  return `<section class="hero"><div><p class="eyebrow">Сообщество для вдумчивого диалога</p><h1>Пространство, где<br>можно <em>быть собой</em></h1><p class="hero__text">Исследуем жизнь, отношения и внутренние перемены — бережно, с уважением к разному опыту.</p><a href="${discussionsHref}" class="button">Перейти к обсуждениям <span>→</span></a></div><div class="hero__aside"><span class="hero__leaf">❋</span><strong>${members}</strong><small>участников сообщества</small><hr><p>Сегодня на форуме<br><b>${todayActive} человек</b></p></div></section><section class="quick-links" aria-label="Быстрая навигация"><a href="#/active">◷ <span><b>Активные темы</b><small>обсуждают сейчас</small></span><em>→</em></a>${participatedLink}</section>${sectionsGroup('Специальные разделы', special, { isAdmin })}${sectionsGroup('Разделы форума', regular, { isAdmin })}`;
};

export const sectionTemplate = (
  section,
  { isAdmin = false } = {},
) => {
  const categories = (section.categories || []).map(
    (category) => ({
      ...category,
      isCategory: true,
      isTopic: false,
    }),
  );
  const adminTools = isAdmin
    ? sectionAdminToolsMarkup(section.id)
    : '';
  return `<div class="breadcrumbs">
      <a href="#/">Форум</a><span>›</span>
      <b>${escapeHtml(section.title)}</b>
    </div>
    <section
      class="category-section standalone"
      data-section-block
      data-section-id="${section.id}"
    >
      <div class="category-heading">
        <h1>${escapeHtml(section.title)}</h1>
        <span class="category-heading__topics">Темы</span>
        <span class="category-heading__posts">Сообщения</span>
        <span>Последнее сообщение</span>
      </div>
      ${adminTools}
      <div class="topic-table">${
        categories.length
          ? categories.map(topicRow).join('')
          : '<p class="replies__empty">В этом разделе пока нет категорий</p>'
      }</div>
    </section>`;
};

const accessPanelTemplate = ({
  entity,
  entityId,
  isRestricted,
}) => {
  if (!isRestricted) {
    return '';
  }
  return `<div
      class="acl-panel"
      data-acl-panel
      data-acl-entity="${escapeHtml(entity)}"
      data-acl-id="${escapeHtml(entityId)}"
    >
      <div class="acl-panel__head">
        <h3>Допущенные пользователи</h3>
        <p class="acl-panel__hint">
          Список сохраняется при открытии и повторном скрытии.
        </p>
      </div>
      <div class="acl-panel__search">
        <input
          type="search"
          data-acl-search
          placeholder="Начните вводить имя или выберите из списка…"
          autocomplete="off"
        >
        <div class="acl-panel__results" data-acl-results></div>
      </div>
      <p class="acl-panel__members-label">Добавлены:</p>
      <ul class="acl-panel__members" data-acl-members>
        <li class="acl-panel__empty" data-acl-empty>
          Пока никого нет — выберите пользователей выше
        </li>
      </ul>
      <p class="compose__error" data-acl-error hidden></p>
    </div>`;
};

const restrictedBadge = (isRestricted) =>
  isRestricted
    ? '<span class="acl-badge" title="Скрыто">Скрыто</span>'
    : '';

export const topicTemplate = (
  topic,
  { isAuthenticated = false } = {},
) => {
  const sectionHref = topic.sectionId
    ? `#/section/${topic.sectionId}`
    : '#/';
  const categoryHref = topic.categoryId
    ? `#/forum/${topic.categoryId}`
    : '#/active';
  const pageData = topic.posts || {
    items: [],
    page: 1,
    totalPages: 0,
    total: 0,
  };
  const closedNote = topic.isClosed
    ? '<p class="topic-page__closed">Тема закрыта для новых ответов.</p>'
    : '';
  const topicDescription = topic.description
    ? `<p class="topic-page__description">${escapeHtml(topic.description)}</p>`
    : '';
  const compose = isAuthenticated && !topic.isClosed
    ? `<form class="compose" data-compose-root>
        <div class="quote-preview" data-quote-preview hidden></div>
        <div class="compose__field">
          <span class="compose__label">Ваш ответ в теме</span>
          ${richEditorMarkup({
            name: 'body',
            placeholder: 'Напишите сообщение…',
            minRows: 4,
          })}
        </div>
        <div class="compose__actions">
          <button class="button" type="submit">Отправить</button>
          <button class="button button--soft" type="button" data-action="cancel-compose">Свернуть</button>
        </div>
        <p class="compose__error" data-error hidden></p>
      </form>`
    : isAuthenticated
      ? ''
      : `<p class="topic-page__login-hint">Чтобы ответить, <a class="login-button" href="#" data-action="login">войдите</a> в аккаунт.</p>`;

  const sectionCrumb = topic.section
    ? `<a href="${sectionHref}">${escapeHtml(topic.section)}</a><span>›</span>`
    : '';
  const visibilityBtn = topic.canManage
    ? `<button
        class="button button--soft"
        type="button"
        data-action="toggle-topic-visibility"
        data-restricted="${topic.isRestricted ? '1' : '0'}"
      >${topic.isRestricted ? 'Открыть' : 'Скрыть'}</button>`
    : '';
  const replyBtn =
    isAuthenticated && !topic.isClosed
      ? '<button class="button button--soft" type="button" data-action="open-compose">Ответить</button>'
      : '';
  const editTitleBtn = topic.canEditTitle
    ? `<button
        class="button button--soft"
        type="button"
        data-action="open-edit-title"
      >Изменить название</button>`
    : '';
  const editTitleForm = topic.canEditTitle
    ? `<form class="topic-title-edit" data-edit-title-form hidden>
        <label class="topic-title-edit__field">
          <span class="topic-title-edit__label">Название темы</span>
          <input
            class="topic-title-edit__input"
            type="text"
            name="title"
            required
            maxlength="200"
            value="${escapeHtml(topic.title)}"
          >
        </label>
        <div class="topic-title-edit__actions">
          <button
            class="button"
            type="button"
            data-action="submit-edit-title"
          >Сохранить</button>
          <button
            class="button button--soft"
            type="button"
            data-action="cancel-edit-title"
          >Отмена</button>
        </div>
        <p class="compose__error" data-error hidden></p>
      </form>`
    : '';

  return `<div class="breadcrumbs">
      <a href="#/">Форум</a><span>›</span>
      ${sectionCrumb}
      <a href="${categoryHref}">${escapeHtml(topic.category)}</a><span>›</span>
      <b data-topic-title-crumb>${escapeHtml(topic.title)}</b>
    </div>
    <section
      class="topic-page"
      data-topic-id="${topic.id}"
      data-topic-closed="${topic.isClosed ? '1' : '0'}"
      data-topic-restricted="${topic.isRestricted ? '1' : '0'}"
      data-can-edit-title="${topic.canEditTitle ? '1' : '0'}"
    >
      <div class="topic-page__head">
        <div>
          <p class="eyebrow">Обсуждение ${restrictedBadge(topic.isRestricted)}</p>
          <h1 data-topic-title>${escapeHtml(topic.title)}</h1>
          ${topicDescription}
          ${closedNote}
        </div>
        <div class="topic-page__actions">
          ${visibilityBtn}
          ${editTitleBtn}
          ${replyBtn}
        </div>
      </div>
      ${editTitleForm}
      ${
        topic.canManage
          ? accessPanelTemplate({
              entity: 'topic',
              entityId: topic.id,
              isRestricted: topic.isRestricted,
            })
          : ''
      }
      ${compose}
      <div class="posts" data-roots>
        ${pageData.items.map((post) => postCardTemplate(post)).join('') || '<p class="replies__empty">Пока нет сообщений. Будьте первым!</p>'}
      </div>
      <div data-roots-pagination>
        ${paginationTemplate({
          page: pageData.page,
          totalPages: pageData.totalPages,
          total: pageData.total,
          prefix: 'roots',
        })}
      </div>
    </section>`;
};

export const listTemplate = (title, items) =>
  `<div class="breadcrumbs"><a href="#/">Форум</a><span>›</span><b>${escapeHtml(title)}</b></div><section class="category-section standalone"><div class="category-heading"><h1>${escapeHtml(title)}</h1><span class="category-heading__topics">Темы</span><span class="category-heading__posts">Сообщения</span><span>Последнее сообщение</span></div><div class="topic-table">${items.map(topicRow).join('')}</div></section>`;

export const forumTemplate = (
  forum,
  { isAuthenticated = false, isAdmin = false } = {},
) => {
  const sectionHref = forum.sectionId
    ? `#/section/${forum.sectionId}`
    : '#/';
  const sectionCrumb = forum.section
    ? `<a href="${sectionHref}">${escapeHtml(forum.section)}</a><span>›</span>`
    : '';
  const description = forum.description
    ? `<div class="forum-page__description">${escapeHtml(forum.description)}</div>`
    : '<div class="forum-page__description"></div>';
  const newTopicButton = isAuthenticated
    ? '<button type="button" class="button" data-action="open-new-topic">Новая тема</button>'
    : '<a class="button" href="#" data-action="login">Новая тема</a>';
  const visibilityBtn = forum.canManage
    ? `<button
        type="button"
        class="button button--soft"
        data-action="toggle-category-visibility"
        data-restricted="${forum.isRestricted ? '1' : '0'}"
      >${forum.isRestricted ? 'Открыть' : 'Скрыть'}</button>`
    : '';
  const adminTopicFields = isAdmin
    ? `<label class="acl-toggle">
        <input
          type="checkbox"
          name="is_restricted"
          data-new-topic-restricted
        >
        <span>Скрытая тема</span>
      </label>
      <div
        class="acl-create"
        data-new-topic-acl
        hidden
      >
        <label>
          <span>Допустить пользователей</span>
          <input
            type="search"
            data-new-topic-search
            placeholder="Начните вводить имя или выберите из списка…"
            autocomplete="off"
          >
        </label>
        <div
          class="acl-panel__results"
          data-new-topic-results
        ></div>
        <p class="acl-panel__members-label">Добавлены:</p>
        <ul
          class="acl-panel__members"
          data-new-topic-members
        ></ul>
      </div>`
    : '';
  const newTopicForm = isAuthenticated
    ? `<form class="compose new-topic-form" data-new-topic-form data-category-id="${forum.id}">
        <label class="compose__field">
          <span class="compose__label">Название темы</span>
          <input
            type="text"
            name="title"
            required
            maxlength="200"
            placeholder="О чём эта тема?"
          >
        </label>
        <div class="compose__field">
          <span class="compose__label">Первое сообщение</span>
          ${richEditorMarkup({
            name: 'body',
            placeholder: 'Напишите сообщение…',
            minRows: 5,
          })}
        </div>
        ${adminTopicFields}
        <div class="compose__actions">
          <button class="button" type="submit">Создать тему</button>
          <button
            class="button button--soft"
            type="button"
            data-action="cancel-new-topic"
          >Отмена</button>
        </div>
        <p class="compose__error" data-error hidden></p>
      </form>`
    : '';
  const meta = `<div class="forum-page__meta">
      ${description}
      <div class="forum-page__meta-spacer" aria-hidden="true"></div>
      <div class="forum-page__toolbar">
        ${visibilityBtn}
        ${newTopicButton}
      </div>
    </div>`;
  const titleHtml = `${escapeHtml(forum.title)} ${restrictedBadge(forum.isRestricted)}`;
  const aclBlock = forum.canManage
    ? accessPanelTemplate({
        entity: 'category',
        entityId: forum.id,
        isRestricted: forum.isRestricted,
      })
    : '';
  return `<div class="breadcrumbs"><a href="#/">Форум</a><span>›</span>${sectionCrumb}<b>${escapeHtml(forum.title)}</b></div><section class="category-section standalone category-section--topics" data-forum-page data-category-id="${forum.id}" data-category-restricted="${forum.isRestricted ? '1' : '0'}"><div class="category-heading"><h1>${titleHtml}</h1><span class="category-heading__topics">Темы</span><span class="category-heading__posts">Сообщения</span><span>Последнее сообщение</span></div>${meta}${aclBlock}${newTopicForm}<div class="topic-table">${forum.topicList.length ? forum.topicList.map(topicRow).join('') : '<p class="replies__empty">В этой категории пока нет тем</p>'}</div></section>`;
};

export const profileTemplate = (profile) => {
  const name = profile.display_name || profile.username;
  const avatarSrc = profile.has_avatar
    ? (profile.avatar_url || `/api/users/${profile.uid}/avatar`)
    : '';
  const avatar = avatarSrc
    ? `<img class="profile-avatar__img" src="${escapeHtml(avatarSrc)}?t=${Date.now()}" alt="">`
    : `<span class="avatar profile-avatar__fallback">${escapeHtml(profile.initials || '?')}</span>`;
  const postsCount = new Intl.NumberFormat('ru-RU').format(
    profile.posts_count ?? 0,
  );
  return `<div class="breadcrumbs">
      <a href="#/">Форум</a><span>›</span>
      <b>Мой профиль</b>
    </div>
    <section class="profile-page">
      <div class="profile-card">
        <div class="profile-card__head">
          <div class="profile-avatar">${avatar}</div>
          <div>
            <p class="eyebrow">Аккаунт</p>
            <h1 data-profile-title>${escapeHtml(name)}</h1>
            <p class="profile-card__meta">@${escapeHtml(profile.username)}</p>
          </div>
        </div>
        <dl class="profile-stats">
          <div>
            <dt>Написано сообщений</dt>
            <dd>${postsCount}</dd>
          </div>
        </dl>
        <form class="profile-form" data-profile-form>
          <label class="auth-field">
            <span>Никнейм</span>
            <input
              type="text"
              name="display_name"
              maxlength="120"
              required
              value="${escapeHtml(profile.display_name || '')}"
            >
          </label>
          <label class="auth-field">
            <span>Фотография</span>
            <input
              type="file"
              name="avatar_file"
              accept="image/jpeg,image/png,image/webp"
            >
          </label>
          <div class="profile-form__actions">
            <button class="button" type="submit">Сохранить</button>
            ${
              profile.has_avatar
                ? `<button
              class="button button--soft"
              type="button"
              data-action="clear-avatar"
            >Убрать фото</button>`
                : ''
            }
          </div>
          <p class="auth-error" data-error hidden></p>
          <p class="auth-success" data-success hidden></p>
        </form>
        <div class="profile-actions">
          <a
            class="button button--soft"
            href="#"
            data-action="change-password"
          >Сменить пароль</a>
        </div>
      </div>
    </section>`;
};

export const publicProfileTemplate = (
  profile,
  { isAuthenticated = false, isSelf = false } = {},
) => {
  const name = profile.display_name || profile.username;
  const avatarSrc = profile.has_avatar
    ? (profile.avatar_url || `/api/users/${profile.uid}/avatar`)
    : '';
  const avatar = avatarSrc
    ? `<img class="profile-avatar__img" src="${escapeHtml(avatarSrc)}" alt="">`
    : `<span class="avatar profile-avatar__fallback">${escapeHtml(profile.initials || '?')}</span>`;
  const postsCount = format(profile.posts_count ?? 0);
  const topicsCount = format(profile.topics_count ?? 0);
  const status = profile.is_active ? 'Активен' : 'Неактивен';
  let messageAction = '';
  if (isAuthenticated && !isSelf) {
    messageAction = `<div class="profile-actions">
      <a
        class="button"
        href="#/chats/new/${escapeHtml(profile.uid)}"
      >Написать личное сообщение</a>
    </div>`;
  } else if (!isAuthenticated) {
    messageAction = `<div class="profile-actions">
      <a
        class="button"
        href="#"
        data-action="login"
      >Войти, чтобы написать</a>
    </div>`;
  }
  return `<div class="breadcrumbs">
      <a href="#/">Форум</a><span>›</span>
      <b>Профиль</b>
    </div>
    <section class="profile-page">
      <div class="profile-card">
        <div class="profile-card__head">
          <div class="profile-avatar">${avatar}</div>
          <div>
            <p class="eyebrow">Участник</p>
            <h1>${escapeHtml(name)}</h1>
            <p class="profile-card__meta">@${escapeHtml(profile.username)}</p>
          </div>
        </div>
        <dl class="profile-stats">
          <div>
            <dt>Зарегистрирован</dt>
            <dd class="profile-stats__text">${escapeHtml(formatProfileDate(profile.created_at))}</dd>
          </div>
          <div>
            <dt>Последнее посещение</dt>
            <dd class="profile-stats__text">${escapeHtml(formatProfileDate(profile.last_seen_at))}</dd>
          </div>
          <div>
            <dt>Сообщений</dt>
            <dd>${postsCount}</dd>
          </div>
          <div>
            <dt>Созданных тем</dt>
            <dd>${topicsCount}</dd>
          </div>
          <div>
            <dt>Статус</dt>
            <dd class="profile-stats__text">${escapeHtml(status)}</dd>
          </div>
        </dl>
        ${messageAction}
      </div>
    </section>`;
};

const chatPeerAvatar = (peer) => {
  if (peer?.avatarUrl) {
    return `<img class="avatar avatar--image chat-row__avatar" src="${escapeHtml(peer.avatarUrl)}" alt="">`;
  }
  return `<span class="avatar chat-row__avatar">${escapeHtml(peer?.initials || '?')}</span>`;
};

const formatChatBadgeCount = (count) => {
  const value = Number(count) || 0;
  if (value <= 0) {
    return '';
  }
  return value > 20 ? '20+' : String(value);
};

export const chatListItemTemplate = (
  chat,
  { activeId = null } = {},
) => {
  const isActive = String(chat.id) === String(activeId);
  const preview = chat.lastMessage?.body
    || 'Нет сообщений';
  const time = chat.lastMessage?.time || chat.updatedTime || '';
  const badgeLabel = formatChatBadgeCount(chat.unreadCount);
  const badgeText = badgeLabel
    ? escapeHtml(badgeLabel)
    : '0';
  const badgeHidden = badgeLabel ? '' : ' hidden';
  const badge = (
    `<span class="chat-row__badge"`
    + ` data-chat-row-badge${badgeHidden}>`
    + `${badgeText}</span>`
  );
  return `<a
    class="chat-row${isActive ? ' is-active' : ''}"
    href="#/chats/${chat.id}"
    data-chat-id="${chat.id}"
  >
    ${chatPeerAvatar(chat.peer)}
    <div class="chat-row__body">
      <div class="chat-row__top">
        <b>${escapeHtml(chat.peer?.displayName || 'Участник')}</b>
        <span>${escapeHtml(time)}</span>
      </div>
      <div class="chat-row__bottom">
        <p class="chat-row__preview">${escapeHtml(preview)}</p>
        ${badge}
      </div>
    </div>
  </a>`;
};

const chatBubbleTemplate = (message) => {
  const mine = message.isMine ? ' chat-bubble--own' : '';
  const unread =
    !message.isMine && !message.readAt
      ? ' data-chat-unread="1"'
      : '';
  return `<div class="chat-bubble${mine}" data-message-id="${message.id}"${unread}>
    <div class="chat-bubble__text">${renderFormattedBody(message.body)}</div>
    <time class="chat-bubble__time">${escapeHtml(message.time || '')}</time>
  </div>`;
};

export const chatsPageTemplate = (
  {
    chats = [],
    activeChatId = null,
    peer = null,
    messages = [],
  } = {},
) => {
  const listHtml = chats.length
    ? chats
        .map((chat) =>
          chatListItemTemplate(chat, {
            activeId: activeChatId,
          }),
        )
        .join('')
    : '<p class="chats-empty">Пока нет диалогов. Напишите кому-нибудь из профиля.</p>';

  let threadHtml = `
    <div class="chats-thread chats-thread--empty">
      <p>Выберите диалог слева или напишите участнику из профиля.</p>
    </div>`;

  if (activeChatId && peer) {
    const avatar = chatPeerAvatar(peer);
    const messagesHtml = messages.length
      ? messages.map(chatBubbleTemplate).join('')
      : '<p class="chats-empty">Напишите первое сообщение</p>';
    threadHtml = `
      <div class="chats-thread" data-chat-thread data-chat-id="${activeChatId}">
        <header class="chats-thread__head">
          <a class="chats-thread__back" href="#/chats" aria-label="К списку чатов">←</a>
          <a class="chats-thread__peer user-link" href="#/users/${escapeHtml(peer.uid)}">
            ${avatar}
            <div>
              <b>${escapeHtml(peer.displayName || 'Участник')}</b>
              <small>@${escapeHtml(peer.username || '')}</small>
            </div>
          </a>
        </header>
        <div class="chats-messages" data-chat-messages>
          ${messagesHtml}
        </div>
        <form class="chats-composer" data-chat-composer data-chat-id="${activeChatId}">
          ${richEditorMarkup({
            name: 'body',
            placeholder: 'Сообщение…',
            minRows: 1,
          })}
          <button class="button" type="submit">Отправить</button>
          <p class="compose__error" data-error hidden></p>
        </form>
      </div>`;
  }

  return `<div class="breadcrumbs">
      <a href="#/">Форум</a><span>›</span>
      <b>Чаты</b>
    </div>
    <section class="chats-layout" data-chats-page>
      <aside class="chats-sidebar">
        <div class="chats-sidebar__head">
          <h1>Чаты</h1>
        </div>
        <div class="chats-list" data-chats-list>
          ${listHtml}
        </div>
      </aside>
      ${threadHtml}
    </section>`;
};

export const contactTemplate = (contact) => {
  const title = contact.title || 'Связаться';
  const authorName = contact.authorName || '';
  const bio = contact.bio || '';
  const photoUrl = contact.photoUrl || '';
  const telegramUrl = contact.telegramUrl || '#';
  const whatsappUrl = contact.whatsappUrl || '#';
  const photo = photoUrl
    ? `<img
        class="contact-page__photo"
        src="${escapeHtml(photoUrl)}"
        alt="${escapeHtml(authorName || 'Фото автора форума')}"
      >`
    : `<div class="contact-page__photo contact-page__photo--placeholder" aria-hidden="true">◌</div>`;
  const nameParts = authorName.trim().split(/\s+/).filter(Boolean);
  const surname = nameParts[0] || '';
  const givenNames = nameParts.slice(1).join(' ');
  const authorHtml = surname
    ? `<p class="contact-card__name">
        <span class="contact-card__name-surname">${escapeHtml(surname)}</span>
        ${
          givenNames
            ? `<span class="contact-card__name-given">${escapeHtml(givenNames)}</span>`
            : ''
        }
      </p>`
    : '';
  return `<div class="breadcrumbs">
      <a href="#/">Форум</a><span>›</span>
      <b>Связаться</b>
    </div>
    <section class="contact-page">
      <article class="contact-card">
        <div class="contact-card__media">
          ${photo}
        </div>
        <div class="contact-card__body">
          <p class="eyebrow">Контакты</p>
          <h1>${escapeHtml(title)}</h1>
          <p class="contact-card__bio">${escapeHtml(bio)}</p>
        </div>
        ${authorHtml}
        <div class="contact-card__actions">
          <a
            class="button contact-card__btn contact-card__btn--telegram"
            href="${escapeHtml(telegramUrl)}"
            target="_blank"
            rel="noopener noreferrer"
          >Telegram</a>
          <a
            class="button button--soft contact-card__btn contact-card__btn--whatsapp"
            href="${escapeHtml(whatsappUrl)}"
            target="_blank"
            rel="noopener noreferrer"
          >WhatsApp</a>
        </div>
      </article>
    </section>`;
};

export const supportTemplate = ({
  email = '',
  emailLocked = false,
  emailMissing = false,
} = {}) => {
  const emailHint = emailMissing
    ? `<p class="support-page__hint support-page__hint--warn">
        В профиле не указан email. Добавьте его в аккаунте,
        чтобы отправить обращение.
      </p>`
    : emailLocked
      ? `<p class="support-page__hint">
          Обращение будет отправлено на email из вашего профиля.
        </p>`
      : `<p class="support-page__hint">
          Укажите email, на который мы сможем ответить.
          Можно отправить не более 2 обращений в сутки.
        </p>`;
  const emailReadonly = emailLocked ? 'readonly' : '';
  const emailRequired = emailLocked ? '' : 'required';
  const submitDisabled = emailMissing ? 'disabled' : '';
  return `<div class="breadcrumbs">
      <a href="#/">Форум</a><span>›</span>
      <b>Техподдержка</b>
    </div>
    <section class="support-page">
      <article class="support-card">
        <p class="eyebrow">Помощь</p>
        <h1>Техническая поддержка</h1>
        <p class="support-card__lead">
          Опишите проблему или вопрос по работе форума.
          Мы ответим на указанный адрес электронной почты.
        </p>
        ${emailHint}
        <form class="support-form" data-support-form>
          <label class="auth-field">
            <span>Тема</span>
            <input
              type="text"
              name="subject"
              maxlength="200"
              required
              placeholder="Кратко опишите тему"
            >
          </label>
          <label class="auth-field">
            <span>Email</span>
            <input
              type="email"
              name="email"
              maxlength="320"
              ${emailRequired}
              ${emailReadonly}
              value="${escapeHtml(email)}"
              placeholder="name@example.com"
            >
          </label>
          <label class="auth-field">
            <span>Сообщение</span>
            <textarea
              name="body"
              rows="8"
              maxlength="5000"
              required
              placeholder="Подробно опишите ситуацию"
            ></textarea>
          </label>
          <div class="support-form__actions">
            <button
              class="button"
              type="submit"
              ${submitDisabled}
            >Отправить</button>
          </div>
          <p class="auth-error" data-error hidden></p>
          <p class="auth-success" data-success hidden></p>
        </form>
      </article>
    </section>`;
};

export const notFoundTemplate = `<section class="empty-state"><span>◌</span><h1>Страница пока не найдена</h1><p>Возможно, она ещё не создана.</p><a class="button" href="#/">Вернуться на главную</a></section>`;

export const rulesTemplate = (sections) => {
  const body = (sections || [])
    .map((section) => {
      const paragraphs = (section.paragraphs || [])
        .map(
          (text) =>
            `<p>${escapeHtml(text)}</p>`,
        )
        .join('');
      const items = section.items?.length
        ? `<ol class="rules-page__list">${section.items
            .map(
              (item) =>
                `<li>${escapeHtml(item)}</li>`,
            )
            .join('')}</ol>`
        : '';
      return `<section class="rules-page__section">
        <h2>${escapeHtml(section.title)}</h2>
        ${paragraphs}
        ${items}
      </section>`;
    })
    .join('');

  return `<div class="breadcrumbs">
      <a href="#/">Форум</a><span>›</span>
      <b>Правила</b>
    </div>
    <article class="rules-page">
      <header class="rules-page__header">
        <h1>Правила форума</h1>
        <p>
          Общие нормы общения для участников
          «Диагностика кармы. Взгляд изнутри».
        </p>
      </header>
      ${body}
    </article>`;
};
