import { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../api.js';

// "Ms. Reyes, Registrar's Office" — but not "Registrar's Office, Registrar's Office".
function answeredBy(ticket) {
  const by = ticket.answered_by?.trim();
  if (!by) return ticket.office_name;
  return by.toLowerCase().includes(ticket.office_name.toLowerCase()) ? by : `${by}, ${ticket.office_name}`;
}

function when(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/** "My questions": everything this student passed to an office, and the answers. */
export default function TicketsPanel({ token }) {
  const [tickets, setTickets] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    apiFetch('/api/tickets', { token })
      .then(setTickets)
      .catch((err) => setError(err.message));
  }, [token]);

  useEffect(load, [load]);

  return (
    <section className="voice-panel" aria-label="My questions">
      <div className="voice-panel-head">
        <h2>My questions</h2>
        <button type="button" className="link-button" onClick={load}>
          Refresh
        </button>
      </div>

      {error && <p className="voice-error">{error}</p>}
      {!tickets && !error && <p className="voice-hint">Loading…</p>}
      {tickets?.length === 0 && (
        <p className="voice-hint">
          Nothing yet. When I can’t answer something, tap “Ask an office” under my reply and I’ll pass your question
          along.
        </p>
      )}

      {tickets?.length > 0 && (
        <ul className="ticket-list">
          {tickets.map((t) => (
            <li key={t.ref} className={`ticket is-${t.status}`}>
              <div className="ticket-top">
                <span className={`ticket-status is-${t.status}`}>
                  {t.status === 'answered' ? 'Answered' : 'Waiting for reply'}
                </span>
                <span className="ticket-meta">
                  {t.office_name} · {t.ref} · {when(t.created_at)}
                </span>
              </div>
              <p className="ticket-question">{t.question}</p>
              {t.answer && (
                <div className="ticket-answer">
                  <p className="ticket-answer-by">
                    {answeredBy(t)} · {when(t.answered_at)}
                  </p>
                  <p className="ticket-answer-text">{t.answer}</p>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
