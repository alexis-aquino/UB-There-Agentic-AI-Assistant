import { useCallback, useEffect, useState } from 'react';
import { API_URL } from '../api.js';

const TOKEN_KEY = 'ub-there-token';

function readToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Private mode: the session just won't survive a reload.
  }
}

async function request(path, { token, body } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}/api/auth${path}`, {
    method: body ? 'POST' : 'GET',
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? 'Please check the form and try again.' : data.detail;
    const error = new Error(detail ?? `Request failed (${res.status})`);
    error.status = res.status;
    throw error;
  }
  return data;
}

/**
 * Session state for the whole app. `status` is 'loading' while a stored token is being
 * checked, then 'signed-in' or 'signed-out'.
 */
export default function useAuth() {
  const [token, setToken] = useState(readToken);
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState(token ? 'loading' : 'signed-out');
  const [config, setConfig] = useState({
    google_client_id: '',
    google_domain: 'ub.edu.ph',
    default_password: '12345678',
    departments: [],
  });

  useEffect(() => {
    request('/config').then(setConfig).catch(() => {});
  }, []);

  useEffect(() => {
    if (!token) return;
    request('/me', { token })
      .then((me) => {
        setUser(me);
        setStatus('signed-in');
      })
      .catch((err) => {
        // Only a rejected token signs you out; a backend that's down shouldn't.
        if (err.status === 401) {
          writeToken(null);
          setToken(null);
        }
        setStatus('signed-out');
      });
    // Only on first load — sign-in sets the user itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startSession = useCallback((data) => {
    writeToken(data.token);
    setToken(data.token);
    setUser(data.user);
    setStatus('signed-in');
    return data;
  }, []);

  const login = useCallback(
    (email, password) => request('/login', { body: { email, password } }).then(startSession),
    [startSession]
  );

  // accountType: 'student' | 'guest' | 'department'; students and departments pick a department.
  const signup = useCallback(
    (name, email, password, accountType = 'guest', department = null) =>
      request('/signup', {
        body: { name, email, password, account_type: accountType, department },
      }).then(startSession),
    [startSession]
  );

  const loginWithGoogle = useCallback(
    (credential) => request('/google', { body: { credential } }).then(startSession),
    [startSession]
  );

  const changePassword = useCallback(
    (currentPassword, newPassword) =>
      request('/password', {
        token,
        body: { current_password: currentPassword, new_password: newPassword },
      }).then(setUser),
    [token]
  );

  const updateName = useCallback(
    (name) => request('/profile', { token, body: { name } }).then(setUser),
    [token]
  );

  const logout = useCallback(() => {
    writeToken(null);
    setToken(null);
    setUser(null);
    setStatus('signed-out');
    window.google?.accounts?.id?.disableAutoSelect();
  }, []);

  return { status, user, token, config, login, signup, loginWithGoogle, changePassword, updateName, logout };
}
