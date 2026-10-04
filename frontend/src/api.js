// Empty by default: the app calls /api on its own address and the Vite dev server
// forwards it to the backend (see vite.config.js). That is what lets a phone on the same
// Wi-Fi use the app — "localhost" on a phone would mean the phone itself.
export const API_URL = import.meta.env.VITE_API_URL || '';

/** JSON request to the backend. Throws an Error with the server's message on failure. */
export async function apiFetch(path, { token, body, method } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, {
    method: method ?? (body ? 'POST' : 'GET'),
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? 'Please check what you entered.' : data.detail;
    throw new Error(detail ?? `Request failed (${res.status})`);
  }
  return data;
}
