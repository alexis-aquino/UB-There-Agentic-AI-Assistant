/**
 * SAMPLE accounts for the admin's Accounts page. The backend's users table has no "last active"
 * or "disabled" yet, so the list is built from the sample query log (who asked, and when) plus a
 * few accounts that were made and never or rarely used. Replace loadAccounts() with an API call
 * returning the same shape once the backend tracks it.
 *
 *   { email, name, role: 'student' | 'admin', signIn: 'UB mail' | 'Google',
 *     createdAt, lastActiveAt | null, questions }
 *
 * Disabling and deleting are kept apart, in this browser: { [email]: { by, at } } each. An account
 * can be deleted once it has been disabled for DELETE_AFTER_DAYS.
 */
import { readStore, writeStore } from './store.js';

const DISABLED_STORE = 'ubt-admin-disabled';
const DELETED_STORE = 'ubt-admin-deleted';
export const DELETE_AFTER_DAYS = 30;
const DAY = 86_400_000;

// Made an account, then stopped (or never started) using the assistant.
const DORMANT = [
  ['Lorenzo Ignacio', 400, 330],
  ['Patricia Yap', 380, null],
  ['Gabriel Ocampo', 300, 250],
  ['Isabel Fernandez', 260, null],
  ['Ramon Aguilar', 220, 160],
  ['Clarisse Tan', 150, null],
  ['Enrique Sison', 120, 100],
  ['Hannah Salazar', 45, null],
];

const emailOf = (name) => `${name.toLowerCase().replace(/\s+/g, '.')}@ub.edu.ph`;

/** All accounts, most recently active first; never-used ones last. */
export async function loadAccounts(records, me, now = new Date()) {
  const byEmail = new Map();
  for (const r of records ?? []) {
    if (!r.student) continue;
    const a = byEmail.get(r.student.email) ?? {
      email: r.student.email,
      name: r.student.name,
      role: 'student',
      firstAsked: r.askedAt,
      lastActiveAt: r.askedAt,
      questions: 0,
    };
    a.questions += 1;
    if (r.askedAt < a.firstAsked) a.firstAsked = r.askedAt;
    if (r.askedAt > a.lastActiveAt) a.lastActiveAt = r.askedAt;
    byEmail.set(a.email, a);
  }

  const accounts = [...byEmail.values()].map(({ firstAsked, ...a }, i) => ({
    ...a,
    signIn: i % 3 === 0 ? 'Google' : 'UB mail',
    createdAt: new Date(new Date(firstAsked) - (10 + ((i * 7) % 40)) * DAY).toISOString(),
  }));

  DORMANT.forEach(([name, madeDaysAgo, lastDaysAgo], i) => {
    accounts.push({
      email: emailOf(name),
      name,
      role: 'student',
      signIn: i % 2 ? 'Google' : 'UB mail',
      createdAt: new Date(now - madeDaysAgo * DAY).toISOString(),
      lastActiveAt: lastDaysAgo === null ? null : new Date(now - lastDaysAgo * DAY).toISOString(),
      questions: lastDaysAgo === null ? 0 : 1 + (i % 3),
    });
  });

  if (me && !accounts.some((a) => a.email.toLowerCase() === me.email.toLowerCase())) {
    accounts.push({
      email: me.email,
      name: me.name,
      role: 'admin',
      signIn: 'UB mail',
      createdAt: new Date(now - 420 * DAY).toISOString(),
      lastActiveAt: now.toISOString(),
      questions: 0,
    });
  }

  return accounts.sort((a, b) => (b.lastActiveAt ?? '').localeCompare(a.lastActiveAt ?? ''));
}

// Two accounts already disabled, so the sample shows both a deletable one and one still waiting.
function sampleDisabled(now = new Date()) {
  const by = 'Office of Student Affairs';
  return {
    [emailOf('Lorenzo Ignacio')]: { by, at: new Date(now - 40 * DAY).toISOString() },
    [emailOf('Gabriel Ocampo')]: { by, at: new Date(now - 12 * DAY).toISOString() },
  };
}

export const loadDisabled = () => readStore(DISABLED_STORE, null) ?? sampleDisabled();
export const saveDisabled = (disabled) => writeStore(DISABLED_STORE, disabled);
export const loadDeleted = () => readStore(DELETED_STORE, {});
export const saveDeleted = (deleted) => writeStore(DELETED_STORE, deleted);

/** Whole days until a disabled account can be deleted; 0 once it can. */
export function daysUntilDeletable(off, now = new Date()) {
  const days = Math.floor((now - new Date(off.at)) / DAY);
  return Math.max(0, DELETE_AFTER_DAYS - days);
}

/** 'disabled', 'inactive' (not used within `days`, or never), or 'active'. */
export function accountState(account, disabled, days, now = new Date()) {
  if (disabled[account.email]) return 'disabled';
  if (!account.lastActiveAt) return 'inactive';
  return now - new Date(account.lastActiveAt) > days * DAY ? 'inactive' : 'active';
}
