/** Turns the query log into the dashboard's monthly report. Pure functions over the records. */

// Where an inquiry is in its life, in staff's words. A record's `status` moves forward only:
//   answered (the chatbot answered it), or rerouted (it couldn't) -> pending (sent to an office,
//   no answer yet) -> resolved (the office answered).
//   closed: still rerouted or pending when the student's account was deleted (set by the backend).
// A flagged inquiry shows as "Offensive or off-topic" whatever its status; clearing the flag
// brings the status back.
export const STATES = {
  answered: { label: 'Answered by chatbot', tone: 'ok' },
  rerouted: { label: 'Rerouted', tone: 'warn' },
  pending: { label: 'Pending', tone: 'wait' },
  resolved: { label: 'Resolved', tone: 'ok' },
  closed: { label: 'Closed', tone: 'muted' },
  flagged: { label: 'Offensive or off-topic', tone: 'danger' },
};

/** The state an inquiry shows: its status, unless it's flagged. */
export const stateOf = (r) => (r.flag ? 'flagged' : r.status);

/** "YYYY-MM" of a date, in the viewer's local time. */
export function monthOf(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/** The `count` months ending with `end` ("YYYY-MM"), oldest first. */
export function monthsEnding(end, count) {
  const [y, m] = end.split('-').map(Number);
  return Array.from({ length: count }, (_, i) => monthOf(new Date(y, m - count + i, 1)));
}

/** For counting repeats: "Uniform policy?" and "uniform  policy" are the same question. */
export function normalize(question) {
  return question.toLowerCase().replace(/[^\w\s]/g, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * The report for a period: one month, a handful of picked months, or all of them.
 * `selected` is the period's months ("YYYY-MM"); the trend grid has exactly those as columns.
 * Month-on-month changes (`before`, `lastMonth`) exist only when a single month is selected.
 */
export function buildReport(records, selected) {
  const period = [...selected].sort();
  const inPeriod = new Set(period);
  const months = period;
  const previous = period.length === 1 ? monthsEnding(period[0], 2)[0] : null;

  // The previous month is tallied too, only for the "vs last month" figures.
  const byMonth = new Map([...months, ...(previous ? [previous] : [])].map((m) => [m, []]));
  for (const r of records) byMonth.get(monthOf(r.askedAt))?.push(r);
  const current = period.flatMap((m) => byMonth.get(m) ?? []);

  const topicCounts = new Map();
  for (const [m, list] of byMonth) {
    for (const r of list) {
      if (!topicCounts.has(r.topic)) topicCounts.set(r.topic, new Map());
      const counts = topicCounts.get(r.topic);
      counts.set(m, (counts.get(m) ?? 0) + 1);
    }
  }
  const topics = [...topicCounts].map(([topic, counts]) => ({
    topic,
    counts: months.map((m) => counts.get(m) ?? 0),
    total: months.reduce((sum, m) => sum + (counts.get(m) ?? 0), 0),
    inPeriod: months.reduce((sum, m) => sum + (counts.get(m) ?? 0), 0),
    lastMonth: previous ? counts.get(previous) ?? 0 : null,
  }));
  topics.sort((a, b) => b.inPeriod - a.inPeriod || b.total - a.total || a.topic.localeCompare(b.topic));

  const tally = (list) => ({
    questions: list.length,
    askers: new Set(list.map((r) => r.student?.email ?? `anon-${r.id}`)).size,
  });
  const volume = months.map((m) => ({ month: m, ...tally(byMonth.get(m)) }));
  const totals = tally(current);
  const before = previous ? { month: previous, ...tally(byMonth.get(previous)) } : null;

  const status = Object.fromEntries(Object.keys(STATES).map((key) => [key, 0]));
  for (const r of current) status[stateOf(r)] += 1;
  const sent = current.filter((r) => r.ticket).length; // sent to an office, whatever came of it

  const repeats = new Map();
  for (const r of current) {
    if (r.flag) continue; // flagged inquiries stay out of the most-asked list
    const key = normalize(r.question);
    const entry = repeats.get(key) ?? { question: r.question, count: 0, last: r };
    entry.count += 1;
    if (r.askedAt > entry.last.askedAt) entry.last = r;
    repeats.set(key, entry);
  }
  const topQuestions = [...repeats.values()].sort((a, b) => b.count - a.count).slice(0, 8);

  return { period, inPeriod, months, volume, totals, before, topics, status, sent, topQuestions };
}

export function filterRecords(records, { months, status, topic, search }) {
  const text = search?.trim().toLowerCase();
  return records.filter(
    (r) =>
      (!months || months.has(monthOf(r.askedAt))) &&
      (!status || stateOf(r) === status) &&
      (!topic || r.topic === topic) &&
      (!text || r.question.toLowerCase().includes(text) || r.student?.name.toLowerCase().includes(text)),
  );
}
