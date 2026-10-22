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
]);

const BLOCK_TAGS = new Set(['DIV', 'P', 'LI']);

let activeEditor = null;
let toolbarEl = null;
let hideTimer = null;

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
 * Очищает HTML до allowlist-тегов без атрибутов.
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
 * Plain text с переносами тоже корректно рендерится.
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

export function hideRichToolbar() {
  if (hideTimer) {
    clearTimeout(hideTimer);
    hideTimer = null;
  }
  if (!toolbarEl) {
    return;
  }
  toolbarEl.classList.remove('is-visible');
  toolbarEl.setAttribute('aria-hidden', 'true');
}

export function clearEditor(editor) {
  if (!editor) {
    hideRichToolbar();
    return;
  }
  editor.innerHTML = '';
  const selection = window.getSelection();
  if (selection) {
    selection.removeAllRanges();
  }
  hideRichToolbar();
}

function showToolbar() {
  const bar = ensureToolbar();
  bar.classList.add('is-visible');
  bar.setAttribute('aria-hidden', 'false');
}

function ensureToolbar() {
  if (toolbarEl) {
    return toolbarEl;
  }
  toolbarEl = document.createElement('div');
  toolbarEl.className = 'rich-toolbar';
  toolbarEl.setAttribute('aria-hidden', 'true');
  toolbarEl.innerHTML = `
    <button type="button" class="rich-toolbar__btn" data-format="bold" title="Жирный"><b>B</b></button>
    <button type="button" class="rich-toolbar__btn" data-format="italic" title="Курсив"><i>I</i></button>
    <button type="button" class="rich-toolbar__btn" data-format="underline" title="Подчёркнутый"><u>U</u></button>
    <button type="button" class="rich-toolbar__btn" data-format="strikeThrough" title="Зачёркнутый"><s>S</s></button>
  `;
  document.body.appendChild(toolbarEl);
  toolbarEl.addEventListener('mousedown', (event) => {
    event.preventDefault();
  });
  toolbarEl.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-format]');
    if (!btn || !activeEditor) {
      return;
    }
    const command = btn.dataset.format;
    activeEditor.focus();
    document.execCommand(command, false, null);
    updateToolbarState();
    syncToolbarToSelection();
  });
  return toolbarEl;
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

function updateToolbarState() {
  const bar = ensureToolbar();
  bar.querySelectorAll('[data-format]').forEach((btn) => {
    const active = document.queryCommandState(
      btn.dataset.format,
    );
    btn.classList.toggle('is-active', active);
  });
}

function syncToolbarToSelection() {
  const selection = window.getSelection();
  if (
    !activeEditor
    || !selection
    || selection.isCollapsed
    || selection.rangeCount === 0
    || !selectionInsideEditor(activeEditor)
  ) {
    hideRichToolbar();
    return;
  }
  const range = selection.getRangeAt(0);
  const rect = range.getBoundingClientRect();
  if (!rect || (rect.width === 0 && rect.height === 0)) {
    hideRichToolbar();
    return;
  }
  if (hideTimer) {
    clearTimeout(hideTimer);
    hideTimer = null;
  }
  showToolbar();
  const bar = ensureToolbar();
  const barRect = bar.getBoundingClientRect();
  let top = window.scrollY + rect.top - barRect.height - 8;
  let left =
    window.scrollX
    + rect.left
    + rect.width / 2
    - barRect.width / 2;
  if (top < window.scrollY + 8) {
    top = window.scrollY + rect.bottom + 8;
  }
  left = Math.max(
    8,
    Math.min(
      left,
      window.scrollX + window.innerWidth - barRect.width - 8,
    ),
  );
  bar.style.top = `${top}px`;
  bar.style.left = `${left}px`;
  updateToolbarState();
}

function handleSelectionChange() {
  const selection = window.getSelection();
  if (
    !selection
    || selection.isCollapsed
    || selection.rangeCount === 0
  ) {
    hideRichToolbar();
    return;
  }
  const editor = editorFromNode(selection.anchorNode);
  if (!editor) {
    hideRichToolbar();
    return;
  }
  activeEditor = editor;
  syncToolbarToSelection();
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

/**
 * Разметка редактора для вставки в шаблоны.
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
  return `<div
      class="rich-editor"
      data-rich-editor
      data-name="${escapeHtml(name)}"
      data-placeholder="${escapeHtml(placeholder)}"
      data-min-rows="${minRows}"
    >
      <div
        class="rich-editor__surface"
        contenteditable="true"
        role="textbox"
        aria-multiline="true"
        data-rich-surface
        data-placeholder="${escapeHtml(placeholder)}"
      >${safe}</div>
    </div>`;
}

export function initRichTextEditor(root = document) {
  ensureToolbar();
  root.querySelectorAll('[data-rich-editor]').forEach((wrap) => {
    if (wrap.dataset.richReady === '1') {
      return;
    }
    const surface = wrap.querySelector('[data-rich-surface]');
    if (!surface) {
      return;
    }
    wrap.dataset.richReady = '1';
    surface.addEventListener('focus', () => {
      activeEditor = surface;
    });
    surface.addEventListener('blur', () => {
      // Небольшая задержка: клик по кнопке тулбара
      // сначала вызывает blur, потом click.
      if (hideTimer) {
        clearTimeout(hideTimer);
      }
      hideTimer = setTimeout(() => {
        if (document.activeElement !== surface) {
          if (activeEditor === surface) {
            activeEditor = null;
          }
          hideRichToolbar();
        }
      }, 120);
    });
    surface.addEventListener('keyup', handleSelectionChange);
    surface.addEventListener('mouseup', handleSelectionChange);
    surface.addEventListener('paste', handlePaste);
    surface.addEventListener('input', () => {
      wrap.classList.toggle(
        'is-empty',
        isEditorEmpty(surface.innerHTML),
      );
      handleSelectionChange();
    });
    wrap.classList.toggle(
      'is-empty',
      isEditorEmpty(surface.innerHTML),
    );
  });
}

document.addEventListener(
  'selectionchange',
  handleSelectionChange,
);

document.addEventListener('mousedown', (event) => {
  const target = event.target;
  if (!(target instanceof Node)) {
    hideRichToolbar();
    return;
  }
  if (toolbarEl?.contains(target)) {
    return;
  }
  const surface = editorFromNode(target);
  if (surface) {
    activeEditor = surface;
    return;
  }
  activeEditor = null;
  hideRichToolbar();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    hideRichToolbar();
  }
});

/**
 * Находит surface редактора внутри формы / контейнера.
 */
export function findEditorSurface(container) {
  return container?.querySelector('[data-rich-surface]')
    || null;
}
