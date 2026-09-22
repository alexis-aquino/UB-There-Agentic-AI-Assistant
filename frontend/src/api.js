const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const USER_KEY = 'ubthere.user';
const ADMIN_KEY = 'ubthere.admin';

function readStore(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    // Private windows and cleared site data both throw here; a signed-out app is
    // the correct fallback.
    return null;
  }
}

function writeStore(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* session stays in memory only */
  }
}

export const session = {
  getUser: () => readStore(USER_KEY),
  setUser: (value) => writeStore(USER_KEY, value),
  getAdmin: () => readStore(ADMIN_KEY),
  setAdmin: (value) => writeStore(ADMIN_KEY, value),
};

async function request(path, { method = 'GET', body, token, isForm = false } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (!isForm && body !== undefined) headers['Content-Type'] = 'application/json';

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });

  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }

  if (!response.ok) {
    const detail = data?.detail;
    // FastAPI validation errors arrive as a list of objects, which render as
    // "[object Object]" if passed straight to the UI.
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg ?? JSON.stringify(d)).join('; ')
      : detail || `Request failed (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

export const api = {
  url: API_URL,

  authConfig: () => request('/api/auth/config'),
  guestSignIn: (full_name, email) =>
    request('/api/auth/guest', { method: 'POST', body: { full_name, email } }),
  studentRegister: (payload) =>
    request('/api/auth/student/register', { method: 'POST', body: payload }),
  studentLogin: (email, password) =>
    request('/api/auth/student/login', { method: 'POST', body: { email, password } }),
  googleSignIn: (id_token) =>
    request('/api/auth/student/google', { method: 'POST', body: { id_token } }),

  chat: (message, token, sessionId) =>
    request('/api/chat', {
      method: 'POST',
      token,
      body: { message, session_id: sessionId },
    }),

  track: (code) => request(`/api/track/${encodeURIComponent(code)}`),

  auditDocument: (file, token, formType = 'generic') => {
    const form = new FormData();
    form.append('file', file);
    form.append('form_type', formType);
    return request('/api/audit-document', { method: 'POST', token, body: form, isForm: true });
  },

  adminLogin: (username, password) =>
    request('/api/admin/login', { method: 'POST', body: { username, password } }),
  adminStats: (token) => request('/api/admin/stats', { token }),
  adminInquiries: (token) => request('/api/admin/inquiries?limit=100', { token }),
  adminEscalations: (token) => request('/api/admin/escalations?limit=100', { token }),
  adminUpdateEscalation: (token, id, payload) =>
    request(`/api/admin/escalations/${id}`, { method: 'PATCH', token, body: payload }),
  adminDepartments: (token) => request('/api/admin/departments', { token }),
  adminUpdateDepartment: (token, id, payload) =>
    request(`/api/admin/departments/${id}`, { method: 'PATCH', token, body: payload }),
  adminDocuments: (token) => request('/api/admin/documents', { token }),
  adminUploadDocument: (token, file) => {
    const form = new FormData();
    form.append('file', file);
    return request('/api/admin/documents', { method: 'POST', token, body: form, isForm: true });
  },
  adminDeleteDocument: (token, id) =>
    request(`/api/admin/documents/${id}`, { method: 'DELETE', token }),
  adminReindex: (token) => request('/api/admin/reindex', { method: 'POST', token }),
};
