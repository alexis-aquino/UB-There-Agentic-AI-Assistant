/** Month names for the report period. Months are "YYYY-MM". */

export const MAX_YEARS = 10; // the most years the year box takes
const MAX_MONTHS = 600; // fifty years; only guards the loop below

const key = (year, month) => `${year}-${String(month).padStart(2, '0')}`;

export function monthName(month, style = 'long') {
  const [y, m] = month.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleString(undefined, { month: style, year: style === 'long' ? 'numeric' : undefined });
}

const short = (m) => monthName(m, 'short');
const andList = (items) => (items.length === 1 ? items[0] : `${items.slice(0, -1).join(', ')} & ${items.at(-1)}`);

/**
 * A period in words, grouped by year: "October 2026", "Jan–Jun 2025", "Nov 2025 – Feb 2026",
 * "2024 & 2026", "Mar 2025 & Jan 2026", "2025 & Jan–Mar 2026".
 */
export function periodName(period) {
  const sorted = [...period].sort();
  if (sorted.length === 1) return monthName(sorted[0]);

  const byYear = new Map();
  for (const m of sorted) {
    const y = m.slice(0, 4);
    if (!byYear.has(y)) byYear.set(y, []);
    byYear.get(y).push(m);
  }
  const years = [...byYear];
  const whole = ([, ms]) => ms.length === 12;

  // One unbroken stretch that crosses a year: "Nov 2025 – Feb 2026" (or "2024–2025" for whole years).
  const unbroken = sorted.length === monthsBetween(sorted[0], sorted.at(-1))?.length;
  if (unbroken && years.length > 1) {
    if (years.every(whole)) return `${years[0][0]}–${years.at(-1)[0]}`;
    return `${short(sorted[0])} ${years[0][0]} – ${short(sorted.at(-1))} ${years.at(-1)[0]}`;
  }

  // Otherwise each year on its own: a whole year by number, else its runs of months.
  return andList(
    years.map(([y, ms]) => {
      if (ms.length === 12) return y;
      const runs = [];
      for (const m of ms) {
        const run = runs.at(-1);
        if (run && +m.slice(5) === +run.at(-1).slice(5) + 1) run.push(m);
        else runs.push([m]);
      }
      const names = runs.map((r) => (r.length === 1 ? short(r[0]) : `${short(r[0])}–${short(r.at(-1))}`));
      return `${years.length > 1 ? names.join(', ') : andList(names)} ${y}`;
    }),
  );
}

/** Every month from `from` to `to`, both "YYYY-MM", oldest first. */
export function monthsBetween(from, to) {
  if (from > to) [from, to] = [to, from];
  const [fy, fm] = from.split('-').map(Number);
  const out = [];
  for (let i = 0; ; i += 1) {
    const d = new Date(fy, fm - 1 + i, 1);
    const month = key(d.getFullYear(), d.getMonth() + 1);
    if (month > to) return out;
    if (out.length === MAX_MONTHS) return null;
    out.push(month);
  }
}

/** "2025" -> ['2025']; "2024-2026" or "2024 to 2026" -> ['2024', '2025', '2026']; else null. */
export function readYears(text) {
  const m = text.trim().match(/^(\d{4})(?:\s*(?:-|–|—|to)\s*(\d{4}))?$/i);
  if (!m) return null;
  let [from, to] = [+m[1], +(m[2] ?? m[1])];
  if (from > to) [from, to] = [to, from];
  if (to - from >= MAX_YEARS) return null;
  return Array.from({ length: to - from + 1 }, (_, i) => String(from + i));
}

/** Every month of the given years, Jan to Dec, oldest year first. */
export function yearMonths(years) {
  return [...years].sort().flatMap((y) => Array.from({ length: 12 }, (_, i) => key(y, i + 1)));
}
