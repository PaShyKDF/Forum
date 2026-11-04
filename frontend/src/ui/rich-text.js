import {
  getEmojiPanelCategories,
  pushRecentEmoji,
} from './emoji-data.js';

const ALLOWED_TAGS = new Set([
  'B',
  'STRONG',
  'I',
  'EM',
  'U',
  'S',
  'STRIKE',
  'DEL',
  'BR',
  'A',
  'SPAN',
]);

const BLOCK_TAGS = new Set(['DIV', 'P', 'LI']);
const FORMAT_COMMANDS = new Set([
  'bold',
  'italic',
  'underline',
  'strikeThrough',
]);

let activeEditor = null;

const escapeHtml = (value) =>
  String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

function unwrap(node) {
  const parent = node.parentNode;
  if (!parent) {
    return;
  }
  while (node.firstChild) {
    parent.insertBefore(node.firstChild, node);
  }
  parent.removeChild(node);
}

function stripAttributes(el) {
  [...el.attributes].forEach((attr) => {
    el.removeAttribute(attr.name);
  });
}

/**
 * Нормализует и проверяет http(s) URL для ссылок.
 *
 * Args:
 *   raw: исходная строка адреса.
 *
 * Returns:
 *   Безопасный URL или null.
 */
function normalizeHttpUrl(raw) {
  const value = String(raw || '').trim();
  if (!value) {
    return null;
  }
  let candidate = value;
  if (!/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(candidate)) {
    candidate = `https://${candidate}`;
  }
  let parsed;
  try {
    parsed = new URL(candidate);
  } catch {
    return null;
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return null;
  }
  return parsed.href;
}

/**
 * Оставляет у <a> только безопасный href и rel/target.
 *
 * Args:
 *   el: элемент A.
 */
function sanitizeAnchor(el) {
  const href = normalizeHttpUrl(el.getAttribute('href'));
  stripAttributes(el);
  if (!href) {
    unwrap(el);
    return;
  }
  el.setAttribute('href', href);
  el.setAttribute('rel', 'noopener noreferrer');
  el.setAttribute('target', '_blank');
}

/**
 * Оставляет у span только class="spoiler".
 *
 * Args:
 *   el: элемент SPAN.
 */
function sanitizeSpoilerSpan(el) {
  const className = (el.getAttribute('class') || '')
    .split(/\s+/)
    .filter(Boolean);
  stripAttributes(el);
  if (!className.includes('spoiler')) {
    unwrap(el);
    return;
  }
  el.setAttribute('class', 'spoiler');
}

/**
 * Очищает HTML до allowlist-тегов.
 *
 * Args:
 *   html: исходный HTML.
 *
 * Returns:
 *   Очищенный HTML.
 */
export function sanitizeRichHtml(html) {
  const template = document.createElement('template');
  template.innerHTML = String(html || '');
  const root = template.content;

  const walk = (parent) => {
    [...parent.childNodes].forEach((child) => {
      if (child.nodeType === Node.TEXT_NODE) {
        return;
      }
      if (child.nodeType !== Node.ELEMENT_NODE) {
        parent.removeChild(child);
        return;
      }
      if (BLOCK_TAGS.has(child.tagName)) {
        walk(child);
        if (child.previousSibling) {
          parent.insertBefore(
            document.createElement('br'),
            child,
          );
        }
        unwrap(child);
        return;
      }
      if (!ALLOWED_TAGS.has(child.tagName)) {
        walk(child);
        unwrap(child);
        return;
      }
      if (child.tagName === 'A') {
        walk(child);
        sanitizeAnchor(child);
        return;
      }
      if (child.tagName === 'SPAN') {
        walk(child);
        sanitizeSpoilerSpan(child);
        return;
      }
      stripAttributes(child);
      if (child.tagName === 'BR') {
        while (child.firstChild) {
          child.removeChild(child.firstChild);
        }
        return;
      }
      walk(child);
    });
  };

  walk(root);
  const holder = document.createElement('div');
  holder.appendChild(root);
  return holder.innerHTML
    .replace(/(?:<br\s*\/?>\s*)+$/gi, '')
    .trim();
}

/**
 * Безопасный HTML для отображения сообщения.
 *
 * Args:
 *   raw: сырой body.
 *
 * Returns:
 *   HTML для вставки в DOM.
 */
export function renderFormattedBody(raw) {
  const value = String(raw ?? '');
  if (!/[<>]/.test(value)) {
    return escapeHtml(value).replaceAll('\n', '<br>');
  }
  const sanitized = sanitizeRichHtml(value);
  if (!sanitized) {
    return escapeHtml(value).replaceAll('\n', '<br>');
  }
  return sanitized;
}

export function isEditorEmpty(html) {
  const text = sanitizeRichHtml(html)
    .replace(/<br\s*\/?>/gi, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/<[^>]+>/g, '')
    .trim();
  return !text;
}

export function getEditorHtml(editor) {
  if (!editor) {
    return '';
  }
  return sanitizeRichHtml(editor.innerHTML);
}

export function setEditorHtml(editor, html) {
  if (!editor) {
    return;
  }
  const value = String(html ?? '');
  if (!/[<>]/.test(value)) {
    editor.innerHTML = escapeHtml(value).replaceAll(
      '\n',
      '<br>',
    );
    return;
  }
  editor.innerHTML = sanitizeRichHtml(value);
}

/**
 * Совместимость: floating-тулбар убран, выделение сбрасывается.
 */
export function hideRichToolbar() {
  const selection = window.getSelection();
  if (selection && !selection.isCollapsed) {
    return;
  }
}

export function clearEditor(editor) {
  if (!editor) {
    return;
  }
  editor.innerHTML = '';
  const selection = window.getSelection();
  if (selection) {
    selection.removeAllRanges();
  }
}

function elementFromNode(node) {
  if (!node) {
    return null;
  }
  return node.nodeType === Node.ELEMENT_NODE
    ? node
    : node.parentElement;
}

function editorFromNode(node) {
  const element = elementFromNode(node);
  return element?.closest('[data-rich-surface]') || null;
}

function selectionInsideEditor(editor) {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || !editor) {
    return false;
  }
  const element = elementFromNode(selection.anchorNode);
  return Boolean(element && editor.contains(element));
}

function updateToolbarState(toolbar, editor) {
  if (!toolbar) {
    return;
  }
  toolbar.querySelectorAll('[data-format]').forEach((btn) => {
    const format = btn.dataset.format;
    let active = false;
    if (FORMAT_COMMANDS.has(format) && editor) {
      active = document.queryCommandState(format);
    }
    if (format === 'spoiler' && editor) {
      active = Boolean(closestSpoiler(editor));
    }
    if (format === 'createLink' && editor) {
      active = Boolean(closestAnchor(editor));
    }
    btn.classList.toggle('is-active', active);
  });
}

function closestSpoiler(editor) {
  const selection = window.getSelection();
  if (!selection || !selection.rangeCount) {
    return null;
  }
  const el = elementFromNode(selection.anchorNode);
  if (!el || !editor.contains(el)) {
    return null;
  }
  return el.closest('span.spoiler');
}

function closestAnchor(editor) {
  const selection = window.getSelection();
  if (!selection || !selection.rangeCount) {
    return null;
  }
  const el = elementFromNode(selection.anchorNode);
  if (!el || !editor.contains(el)) {
    return null;
  }
  return el.closest('a');
}

function wrapSelectionWithSpoiler(editor) {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) {
    return;
  }
  const existing = closestSpoiler(editor);
  if (existing) {
    unwrap(existing);
    return;
  }
  if (selection.isCollapsed) {
    return;
  }
  const range = selection.getRangeAt(0);
  const spoiler = document.createElement('span');
  spoiler.className = 'spoiler';
  try {
    range.surroundContents(spoiler);
  } catch {
    const fragment = range.extractContents();
    spoiler.appendChild(fragment);
    range.insertNode(spoiler);
  }
  selection.removeAllRanges();
  const next = document.createRange();
  next.selectNodeContents(spoiler);
  selection.addRange(next);
}

function applyLink(editor) {
  const selection = window.getSelection();
  if (!selection || !selectionInsideEditor(editor)) {
    return;
  }
  const existing = closestAnchor(editor);
  const currentHref = existing?.getAttribute('href') || '';
  const raw = window.prompt(
    'Адрес ссылки',
    currentHref || 'https://',
  );
  if (raw === null) {
    return;
  }
  const href = normalizeHttpUrl(raw);
  if (!href) {
    window.alert('Укажите корректный http(s) адрес');
    return;
  }
  if (existing) {
    existing.setAttribute('href', href);
    existing.setAttribute('rel', 'noopener noreferrer');
    existing.setAttribute('target', '_blank');
    return;
  }
  if (selection.isCollapsed) {
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.rel = 'noopener noreferrer';
    anchor.target = '_blank';
    anchor.textContent = href;
    const range = selection.getRangeAt(0);
    range.insertNode(anchor);
    selection.removeAllRanges();
    const next = document.createRange();
    next.setStartAfter(anchor);
    next.collapse(true);
    selection.addRange(next);
    return;
  }
  document.execCommand('createLink', false, href);
  editor.querySelectorAll('a').forEach((anchor) => {
    const safe = normalizeHttpUrl(anchor.getAttribute('href'));
    if (!safe) {
      unwrap(anchor);
      return;
    }
    anchor.setAttribute('href', safe);
    anchor.setAttribute('rel', 'noopener noreferrer');
    anchor.setAttribute('target', '_blank');
  });
}

function handlePaste(event) {
  event.preventDefault();
  const text =
    event.clipboardData?.getData('text/html')
    || event.clipboardData?.getData('text/plain')
    || '';
  let html;
  if (text.includes('<')) {
    html = sanitizeRichHtml(text);
  } else {
    html = escapeHtml(text).replaceAll('\n', '<br>');
  }
  document.execCommand('insertHTML', false, html || '');
}

function toolbarMarkup() {
  const btn = (format, tip, label, extraClass = '') => {
    const cls = extraClass
      ? `rich-toolbar__btn ${extraClass}`
      : 'rich-toolbar__btn';
    return `<button
      type="button"
      class="${cls}"
      data-format="${format}"
      data-tip="${escapeHtml(tip)}"
      aria-label="${escapeHtml(tip)}"
    >${label}</button>`;
  };
  return `<div class="rich-toolbar" role="toolbar" aria-label="Форматирование">
    ${btn('bold', 'Жирный', '<b>B</b>')}
    ${btn('italic', 'Курсив', '<i>I</i>')}
    ${btn('underline', 'Подчёркнутый', '<u>U</u>')}
    ${btn('strikeThrough', 'Зачёркнутый', '<s>S</s>')}
    ${btn(
      'spoiler',
      'Скрыть текст под спойлером',
      'Спойлер',
      'rich-toolbar__btn--label',
    )}
    ${btn(
      'createLink',
      'Вставить ссылку',
      'Ссылка',
      'rich-toolbar__btn--label',
    )}
    <button
      type="button"
      class="rich-toolbar__btn rich-toolbar__btn--label rich-toolbar__btn--emoji"
      data-action="toggle-emoji-panel"
      data-tip="Смайлики"
      aria-label="Смайлики"
      aria-expanded="false"
    >Смайлики</button>
  </div>`;
}

function emojiPanelMarkup() {
  const categories = getEmojiPanelCategories();
  const activeId = categories[0]?.id || 'recent';
  const tabs = categories.map((category) => {
    const isActive = category.id === activeId;
    return `<button
      type="button"
      class="emoji-panel__tab${isActive ? ' is-active' : ''}"
      data-emoji-category="${escapeHtml(category.id)}"
      title="${escapeHtml(category.title)}"
      aria-label="${escapeHtml(category.title)}"
    >${category.icon}</button>`;
  }).join('');
  const active = categories.find((item) => item.id === activeId)
    || categories[0];
  const grid = (active?.items || []).map((emoji) => (
    `<button
      type="button"
      class="emoji-panel__item"
      data-emoji="${escapeHtml(emoji)}"
      aria-label="${escapeHtml(emoji)}"
    >${emoji}</button>`
  )).join('');
  return `<aside
      class="emoji-panel"
      data-emoji-panel
      aria-label="Смайлики"
    >
      <div class="emoji-panel__tabs" role="tablist">
        ${tabs}
      </div>
      <div
        class="emoji-panel__grid"
        data-emoji-grid
        data-active-category="${escapeHtml(activeId)}"
      >${grid}</div>
    </aside>`;
}

/**
 * Разметка редактора для вставки в шаблоны.
 *
 * Args:
 *   options: name, placeholder, initialHtml, minRows.
 *
 * Returns:
 *   HTML строка редактора с тулбаром и панелью смайликов.
 */
export function richEditorMarkup({
  name = 'body',
  placeholder = 'Напишите сообщение…',
  initialHtml = '',
  minRows = 4,
} = {}) {
  const safe = initialHtml
    ? renderFormattedBody(initialHtml)
    : '';
  return `<div class="rich-composer" data-rich-composer>
      <div
        class="rich-editor"
        data-rich-editor
        data-name="${escapeHtml(name)}"
        data-placeholder="${escapeHtml(placeholder)}"
        data-min-rows="${minRows}"
      >
        ${toolbarMarkup()}
        <div
          class="rich-editor__surface"
          contenteditable="true"
          role="textbox"
          aria-multiline="true"
          data-rich-surface
          data-placeholder="${escapeHtml(placeholder)}"
        >${safe}</div>
      </div>
      ${emojiPanelMarkup()}
    </div>`;
}

function renderEmojiGrid(grid, categoryId) {
  if (!grid) {
    return;
  }
  const categories = getEmojiPanelCategories();
  const category = categories.find((item) => item.id === categoryId)
    || categories[0];
  const items = category?.items || [];
  grid.dataset.activeCategory = category?.id || 'recent';
  grid.innerHTML = items.map((emoji) => (
    `<button
      type="button"
      class="emoji-panel__item"
      data-emoji="${escapeHtml(emoji)}"
      aria-label="${escapeHtml(emoji)}"
    >${emoji}</button>`
  )).join('');
}

function setEmojiPanelOpen(composer, open) {
  if (!composer) {
    return;
  }
  composer.classList.toggle('is-emoji-open', open);
  const toggle = composer.querySelector(
    '[data-action="toggle-emoji-panel"]',
  );
  if (toggle) {
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
}

function insertEmojiAtSelection(surface, emoji) {
  if (!surface || !emoji) {
    return;
  }
  surface.focus();
  const inserted = document.execCommand(
    'insertText',
    false,
    emoji,
  );
  if (!inserted) {
    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0) {
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const node = document.createTextNode(emoji);
      range.insertNode(node);
      range.setStartAfter(node);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
    } else {
      surface.appendChild(document.createTextNode(emoji));
    }
  }
  pushRecentEmoji(emoji);
}

function bindEmojiPanel(composer, surface) {
  const panel = composer.querySelector('[data-emoji-panel]');
  if (!panel || panel.dataset.emojiBound === '1') {
    return;
  }
  panel.dataset.emojiBound = '1';
  const grid = panel.querySelector('[data-emoji-grid]');
  const tabs = panel.querySelector('.emoji-panel__tabs');

  panel.addEventListener('mousedown', (event) => {
    event.preventDefault();
  });

  tabs?.addEventListener('click', (event) => {
    const tab = event.target.closest('[data-emoji-category]');
    if (!tab) {
      return;
    }
    const categoryId = tab.dataset.emojiCategory;
    tabs.querySelectorAll('.emoji-panel__tab').forEach((node) => {
      node.classList.toggle(
        'is-active',
        node === tab,
      );
    });
    if (categoryId === 'recent') {
      renderEmojiGrid(grid, 'recent');
      return;
    }
    renderEmojiGrid(grid, categoryId);
  });

  panel.addEventListener('click', (event) => {
    const item = event.target.closest('[data-emoji]');
    if (!item) {
      return;
    }
    activeEditor = surface;
    insertEmojiAtSelection(surface, item.dataset.emoji);
    const activeCategory = grid?.dataset.activeCategory;
    if (activeCategory === 'recent') {
      renderEmojiGrid(grid, 'recent');
    }
    const wrap = composer.querySelector('[data-rich-editor]');
    wrap?.classList.toggle(
      'is-empty',
      isEditorEmpty(surface.innerHTML),
    );
  });

  const toggle = composer.querySelector(
    '[data-action="toggle-emoji-panel"]',
  );
  toggle?.addEventListener('mousedown', (event) => {
    event.preventDefault();
  });
  toggle?.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    const open = !composer.classList.contains('is-emoji-open');
    if (open) {
      document.querySelectorAll('[data-rich-composer].is-emoji-open')
        .forEach((node) => {
          if (node !== composer) {
            setEmojiPanelOpen(node, false);
          }
        });
      const recentTab = panel.querySelector(
        '[data-emoji-category="recent"]',
      );
      if (recentTab) {
        tabs?.querySelectorAll('.emoji-panel__tab')
          .forEach((node) => {
            node.classList.toggle(
              'is-active',
              node === recentTab,
            );
          });
        renderEmojiGrid(grid, 'recent');
      }
    }
    setEmojiPanelOpen(composer, open);
    if (open) {
      surface.focus();
    }
  });
}

function bindToolbar(wrap, surface) {
  const toolbar = wrap.querySelector('.rich-toolbar');
  if (!toolbar || toolbar.dataset.richBound === '1') {
    return;
  }
  toolbar.dataset.richBound = '1';
  toolbar.addEventListener('mousedown', (event) => {
    event.preventDefault();
  });
  toolbar.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-format]');
    if (!btn) {
      return;
    }
    activeEditor = surface;
    surface.focus();
    const format = btn.dataset.format;
    if (FORMAT_COMMANDS.has(format)) {
      document.execCommand(format, false, null);
    } else if (format === 'spoiler') {
      wrapSelectionWithSpoiler(surface);
    } else if (format === 'createLink') {
      applyLink(surface);
    }
    updateToolbarState(toolbar, surface);
    wrap.classList.toggle(
      'is-empty',
      isEditorEmpty(surface.innerHTML),
    );
  });
}

/**
 * Инициализирует contenteditable-редакторы в контейнере.
 *
 * Args:
 *   root: корень поиска редакторов.
 */
export function initRichTextEditor(root = document) {
  root.querySelectorAll('[data-rich-editor]').forEach((wrap) => {
    if (wrap.dataset.richReady === '1') {
      return;
    }
    const surface = wrap.querySelector('[data-rich-surface]');
    if (!surface) {
      return;
    }
    wrap.dataset.richReady = '1';
    const composer = wrap.closest('[data-rich-composer]')
      || wrap.parentElement;
    bindToolbar(wrap, surface);
    if (composer?.hasAttribute('data-rich-composer')) {
      bindEmojiPanel(composer, surface);
    }
    const toolbar = wrap.querySelector('.rich-toolbar');
    surface.addEventListener('focus', () => {
      activeEditor = surface;
      updateToolbarState(toolbar, surface);
    });
    surface.addEventListener('keyup', () => {
      updateToolbarState(toolbar, surface);
    });
    surface.addEventListener('mouseup', () => {
      updateToolbarState(toolbar, surface);
    });
    surface.addEventListener('paste', handlePaste);
    surface.addEventListener('input', () => {
      wrap.classList.toggle(
        'is-empty',
        isEditorEmpty(surface.innerHTML),
      );
      updateToolbarState(toolbar, surface);
    });
    wrap.classList.toggle(
      'is-empty',
      isEditorEmpty(surface.innerHTML),
    );
  });
}

document.addEventListener('click', (event) => {
  const target = event.target;
  if (!(target instanceof Element)) {
    return;
  }
  if (target.closest('[data-emoji-panel]')) {
    return;
  }
  if (target.closest('[data-action="toggle-emoji-panel"]')) {
    return;
  }
  document.querySelectorAll('[data-rich-composer].is-emoji-open')
    .forEach((composer) => {
      setEmojiPanelOpen(composer, false);
    });
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') {
    return;
  }
  document.querySelectorAll('[data-rich-composer].is-emoji-open')
    .forEach((composer) => {
      setEmojiPanelOpen(composer, false);
    });
});

/**
 * Раскрывает спойлер по клику или Enter/Space.
 *
 * Args:
 *   event: событие click/keydown.
 */
export function handleSpoilerReveal(event) {
  const spoiler = event.target.closest('.spoiler');
  if (!spoiler) {
    return;
  }
  if (spoiler.closest('[data-rich-surface]')) {
    return;
  }
  if (event.type === 'keydown') {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }
  }
  if (spoiler.classList.contains('is-revealed')) {
    return;
  }
  // Не переходить по ссылке, внутри которой / которой обёрнут спойлер
  event.preventDefault();
  event.stopPropagation();
  spoiler.classList.add('is-revealed');
  spoiler.setAttribute('aria-expanded', 'true');
}

document.addEventListener('click', handleSpoilerReveal, true);
document.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' || event.key === ' ') {
    handleSpoilerReveal(event);
  }
}, true);

/**
 * Делает спойлеры в контейнере фокусируемыми.
 *
 * Args:
 *   root: корень поиска.
 */
export function prepareSpoilers(root = document) {
  root.querySelectorAll('.spoiler:not([data-spoiler-ready])')
    .forEach((el) => {
      el.dataset.spoilerReady = '1';
      el.setAttribute('tabindex', '0');
      el.setAttribute('role', 'button');
      el.setAttribute('aria-expanded', 'false');
      el.setAttribute(
        'aria-label',
        'Спойлер, нажмите чтобы открыть',
      );
    });
}

/**
 * Находит surface редактора внутри формы / контейнера.
 *
 * Args:
 *   container: родительский элемент.
 *
 * Returns:
 *   Surface или null.
 */
export function findEditorSurface(container) {
  return container?.querySelector('[data-rich-surface]')
    || null;
}
