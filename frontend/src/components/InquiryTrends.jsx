import { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../api.js';

// Inquiry trends from the query log, shared by the admin overview (every question) and the
// department dashboard (only questions about that office).

export const RANGES = [7, 14, 30];

export function shortDay(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

export function when(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function Stat({ label, value, note }) {
  return (
    <div className="stat">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {note && <p className="stat-note">{note}</p>}
    </div>
  );
}

/** Questions per day: one series, so the title names it and no legend is needed. */
export function DailyChart({ days }) {
  const [hover, setHover] = useState(null);
  const [asTable, setAsTable] = useState(false);
  const max = Math.max(1, ...days.map((d) => d.asked));
  const labelEvery = days.length > 14 ? 5 : days.length > 7 ? 2 : 1;

  return (
    <figure className="chart">
      <figcaption className="chart-head">
        <h3>Questions per day</h3>
        <button type="button" className="link-button" onClick={() => setAsTable((v) => !v)}>
          {asTable ? 'Show as chart' : 'Show as table'}
        </button>
      </figcaption>

      {asTable ? (
        <table className="dash-table">
          <thead>
            <tr>
              <th scope="col">Day</th>
              <th scope="col">Asked</th>
              <th scope="col">Answered by the handbook</th>
            </tr>
          </thead>
          <tbody>
            {days.map((d) => (
              <tr key={d.day}>
                <td>{shortDay(d.day)}</td>
                <td>{d.asked}</td>
                <td>{d.answered}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="chart-plot" onMouseLeave={() => setHover(null)}>
          <span className="chart-max" aria-hidden="true">
            {max}
          </span>
          <div className="chart-bars" role="img" aria-label={`Questions per day, highest ${max}`}>
            {days.map((d, i) => (
              // The whole column is the hit target, not just the bar.
              <div
                key={d.day}
                className="chart-col"
                onMouseEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                tabIndex={0}
                aria-label={`${shortDay(d.day)}: ${d.asked} asked, ${d.answered} answered`}
              >
                <div className="chart-bar" style={{ height: `${(d.asked / max) * 100}%` }} />
                {hover === i && (
                  <div className="chart-tip" role="tooltip">
                    <strong>{shortDay(d.day)}</strong>
                    <span>{d.asked} asked</span>
                    <span>{d.answered} answered by the handbook</span>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="chart-axis" aria-hidden="true">
            {days.map((d, i) => (
              <span key={d.day}>{i % labelEvery === 0 ? shortDay(d.day) : ''}</span>
            ))}
          </div>
        </div>
      )}
    </figure>
  );
}

/** Loads a report (`/api/admin/report` or `/api/department/report`) for the chosen period. */
export function useReport(path, token) {
  const [days, setDays] = useState(14);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    apiFetch(`${path}?days=${days}`, { token })
      .then(setReport)
      .catch((err) => setError(err.message));
  }, [path, token, days]);

  useEffect(load, [load]);
  return { days, setDays, report, error, load };
}

export function RangePicker({ days, setDays, onRefresh }) {
  return (
    <div className="dash-filters" role="group" aria-label="Period">
      {RANGES.map((n) => (
        <button key={n} type="button" className="dash-filter" aria-pressed={days === n} onClick={() => setDays(n)}>
          Last {n} days
        </button>
      ))}
      <button type="button" className="link-button" onClick={onRefresh}>
        Refresh
      </button>
    </div>
  );
}

export function handbookRate(inquiries) {
  return inquiries.asked ? Math.round((inquiries.answered / inquiries.asked) * 100) : null;
}

export function UnansweredList({ inquiries, hint }) {
  return (
    <>
      <h3>Not in the handbook</h3>
      <p className="voice-hint">{hint}</p>
      {inquiries.unanswered.length === 0 ? (
        <p className="voice-hint">None in this period.</p>
      ) : (
        <ul className="ticket-list">
          {inquiries.unanswered.map((q) => (
            <li key={q.question} className="ticket">
              <span className="ticket-meta">
                {q.count === 1 ? 'Asked once' : `Asked ${q.count} times`} · last {when(q.last_asked)}
              </span>
              <p className="ticket-question">{q.question}</p>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export function TopSources({ inquiries }) {
  return (
    <>
      <h3>Most-cited handbook pages</h3>
      {inquiries.top_sources.length === 0 ? (
        <p className="voice-hint">None in this period.</p>
      ) : (
        <table className="dash-table">
          <tbody>
            {inquiries.top_sources.map((s) => (
              <tr key={s.source}>
                <td>{s.source}</td>
                <td className="num">{s.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
