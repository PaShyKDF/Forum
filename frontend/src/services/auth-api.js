import { API_BASE_URL } from '../config.js';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers: {
      Accept: 'application/json',
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

export const authApi = {
  /**
   * Полный URL старта OIDC (редирект браузера в Keycloak).
   * По умолчанию возвращает на текущую SPA-страницу.
   */
  startUrl(returnPath) {
    let next = returnPath ?? (location.hash || '#/');
    if (next === '#/login' || next.startsWith('#/login?')) {
      next = '#/';
    }
    const params = new URLSearchParams({ next });
    return `${API_BASE_URL}/api/auth/start?${params.toString()}`;
  },

  me() {
    return request('/api/auth/me', { method: 'GET' });
  },

  /** SSO-выход через Keycloak (полная навигация). */
  logoutUrl() {
    return `${API_BASE_URL}/api/logout`;
  },

  getProfile() {
    return request('/api/users/me', { method: 'GET' });
  },

  updateProfile(displayName) {
    return request('/api/users/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: displayName }),
    });
  },

  uploadProfileAvatar(file) {
    const body = new FormData();
    body.append('file', file);
    return request('/api/users/me/avatar', {
      method: 'POST',
      body,
    });
  },

  deleteProfileAvatar() {
    return request('/api/users/me/avatar', {
      method: 'DELETE',
    });
  },

  getChangePasswordUrl() {
    return request('/api/users/me/change-password-url', {
      method: 'GET',
    });
  },
};
