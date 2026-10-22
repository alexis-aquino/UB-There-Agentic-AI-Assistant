/** Admin changes kept in this browser until the backend stores them. Storage can be refused
 * (private windows, blocked site data), so every read falls back and every write is best-effort. */

export function readStore(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

/** True if saved. False when the browser refuses (full, private window): the change still holds for this visit. */
export function writeStore(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

/** "today", "3 days ago", "5 months ago", "over a year ago". */
export function ago(iso, now = new Date()) {
  if (!iso) return 'Never';
  const days = Math.floor((now - new Date(iso)) / 86_400_000);
  if (days < 1) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 31) return `${days} days ago`;
  const months = Math.floor(days / 30.4);
  if (months < 12) return `${months} month${months === 1 ? '' : 's'} ago`;
  const years = Math.floor(months / 12);
  return `${years === 1 ? 'Over a year' : `${years} years`} ago`;
}

export function day(iso) {
  return iso ? new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
}
