import { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../api.js';
import { RANGES, when } from './InquiryTrends.jsx';

const KINDS = [
  { id: 'all', label: 'Everything' },
  { id: 'question', label: 'Questions' },
  { id: 'not_found', label: 'Not in the handbook' },
  { id: 'document', label: 'Document checks' },
];

const OUTCOMES = {
  answered: { label: 'Answered', className: 'is-answered' },
  not_found: { label: 'Not in the handbook', className: 'is-open' },
  passed: { label: 'Document complete', className: 'is-answered' },
  needs_fixing: { label: 'Document needs fixing', className: 'is-open' },
  denied: { label: 'Document not in the handbook', className: 'is-open' },
  unreadable: { label: 'Photo unreadable', className: 'is-open' },
};

/** The student query logs (DFD 6.0): each question and document check, newest first.
 *  `path` is /api/admin/logs (everything) or /api/department/logs (one office's). */
export default function QueryLog({ path, token, hint }) {
  const [days, setDays] = useState(14);
  const [search, setSearch] = useState('');
  const [applied, setApplied] = useState('');
  const [kind, setKind] = useState('all');
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    apiFetch(`${path}?days=${days}&q=${encodeURIComponent(applied)}`, { token })
      .then((body) => setEntries(body.entries))
      .catch((err) => setError(err.message));
  }, [path, token, days, applied]);

  useEffect(load, [load]);

  const shown = (entries ?? []).filter((e) =>
    kind === 'all' ? true : kind === 'not_found' ? e.outcome === 'not_found' : e.kind === kind,
  );

  return (
    <>
      {hint && <p className="voice-hint">{hint}</p>}
      <div className="dash-filters" role="group" aria-label="Period">
        {RANGES.map((n) => (
          <button key={n} type="button" className="dash-filter" aria-pressed={days === n} onClick={() => setDays(n)}>
            Last {n} days
          </button>
        ))}
        <form
          className="dash-search-form"
          onSubmit={(e) => {
            e.preventDefault();
            setApplied(search.trim());
          }}
        >
          <input
            className="dash-search"
            type="search"
            placeholder="Search questions"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            maxLength={100}
            aria-label="Search the query log"
          />
        </form>
        <button type="button" className="link-button" onClick={load}>
          Refresh
        </button>
      </div>
      <div className="dash-filters" role="group" aria-label="Show">
        {KINDS.map((k) => (
          <button
            key={k.id}
            type="button"
            className="dash-filter"
            aria-pressed={kind === k.id}
            onClick={() => setKind(k.id)}
          >
            {k.label}
          </button>
        ))}
      </div>

      {error && <p className="voice-error">{error}</p>}
      {!entries && !error && <p className="voice-hint">Loading…</p>}
      {entries && shown.length === 0 && <p className="voice-hint">Nothing in this period.</p>}
      {shown.length > 0 && (
        <table className="dash-table dash-log">
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">Student</th>
              <th scope="col">Question or document</th>
              <th scope="col">Result</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((e, i) => {
              const outcome = OUTCOMES[e.outcome] ?? { label: e.outcome, className: 'is-open' };
              return (
                <tr key={`${e.at}-${i}`}>
                  <td className="docs-when">{when(e.at)}</td>
                  <td>{e.student}</td>
                  <td>
                    {e.kind === 'document' ? <span className="ticket-meta">Document check · </span> : null}
                    {e.text}
                    {e.source && <div className="ticket-meta">{e.source}</div>}
                    {e.missing.length > 0 && <div className="ticket-meta">Missing: {e.missing.join('; ')}</div>}
                  </td>
                  <td>
                    <span className={`ticket-status ${outcome.className}`}>{outcome.label}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {entries && entries.length >= 300 && (
        <p className="voice-hint">Showing the latest 300. Narrow the period or search to see others.</p>
      )}
    </>
  );
}
