/**
 * Accounts for the admin's Accounts page, from the backend (/api/admin/accounts, administrators
 * only). Every call returns the whole list again, so the page always shows what's stored:
 *
 *   { accounts: [{ id, email, name, role: 'admin' | 'department' | 'student' | 'guest',
 *                  department | null, pending (a department waiting for approval),
 *                  signIn: 'UB mail' | 'Email & password', createdAt, lastActiveAt | null,
 *                  questions, disabled: { by, at } | null }],
 *     deleteAfterDays }
 *
 * A disabled account can't sign in and is signed out where it already is. It can be deleted
 * once it has been disabled for deleteAfterDays; the backend enforces both.
 */
import { apiFetch } from '../api.js';

const DAY = 86_400_000;

export const loadAccounts = (token) => apiFetch('/api/admin/accounts', { token });

const act = (action) => (token, ids) => apiFetch(`/api/admin/accounts/${action}`, { token, body: { ids } });
export const disableAccounts = act('disable');
export const enableAccounts = act('enable');
export const deleteAccounts = act('delete');
export const approveAccounts = act('approve');

/** Whole days until a disabled account can be deleted; 0 once it can. */
export function daysUntilDeletable(off, wait, now = new Date()) {
  const days = Math.floor((now - new Date(off.at)) / DAY);
  return Math.max(0, wait - days);
}

/** 'disabled', 'inactive' (not used within `days`, or never), or 'active'. */
export function accountState(account, days, now = new Date()) {
  if (account.disabled) return 'disabled';
  if (!account.lastActiveAt) return 'inactive';
  return now - new Date(account.lastActiveAt) > days * DAY ? 'inactive' : 'active';
}
