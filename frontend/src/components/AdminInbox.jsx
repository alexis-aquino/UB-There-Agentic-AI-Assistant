import { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../api.js';

const FILTERS = [
  ['open', 'Waiting'],
  ['answered', 'Answered'],
];

function when(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

// The draft lives in AdminInbox, so it survives closing the question and opening it again.
function AnswerForm({ ticket, token, text, setText, onAnswered, onHide }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const send = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onAnswered(await apiFetch(`/api/admin/tickets/${ticket.ref}/answer`, { token, body: { answer: text.trim() } }));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <form className="account-form adm-answer-form" onSubmit={send}>
      <label className="auth-field">
        <span>Your answer</span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={7}
          maxLength={5000}
          required
          autoFocus
        />
      </label>
      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}
      <div className="adm-callout-actions">
        <button type="submit" className="button-primary" disabled={busy || !text.trim()}>
          {busy ? 'Sending…' : 'Send answer'}
        </button>
        <button type="button" className="link-button" onClick={onHide}>
          Hide
        </button>
      </div>
    </form>
  );
}

/** "Questions to answer": what students sent this office or department when the chatbot couldn't
 * answer. The answer goes straight to the student's "My questions". Administrators see every one,
 * and can answer for an office or department that has no account yet. */
// office: the office or department this account answers for; none for administrators (all of them).
export default function AdminInbox({ token, office }) {
  const [tickets, setTickets] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [filter, setFilter] = useState('open');
  // Waiting questions show only the question; picking one opens it to answer. One at a time.
  const [openRef, setOpenRef] = useState(null);
  const [drafts, setDrafts] = useState({}); // ref -> answer typed so far

  const load = useCallback(() => {
    setLoadError(null);
    apiFetch('/api/admin/tickets', { token })
      .then(setTickets)
      .catch((err) => setLoadError(err.message));
  }, [token]);

  useEffect(load, [load]);

  if (loadError) return <p className="voice-hint">Couldn’t load the questions: {loadError}</p>;
  if (!tickets) return <p className="voice-hint">Loading the questions…</p>;

  // Closed ones (the student's account was deleted) can't be answered, so they don't wait.
  const waiting = tickets.filter((t) => t.status !== 'answered' && !t.closed);
  const answered = tickets.filter((t) => t.status === 'answered');
  const counts = { open: waiting.length, answered: answered.length };
  const shown = filter === 'open' ? waiting : filter === 'answered' ? answered : tickets;

  const canAnswer = (t) => t.status !== 'answered' && !t.closed;
  const onAnswered = (updated) => setTickets((prev) => prev.map((t) => (t.ref === updated.ref ? updated : t)));

  return (
    <section className="adm-section adm-page" aria-labelledby="adm-inbox-title">
      <div className="adm-tracker-head">
        <div>
          <h3 id="adm-inbox-title">Questions to answer</h3>
          <p className="adm-sub">
            {office
              ? `Questions students sent the ${office} because the chatbot couldn’t answer them from the handbook. Your answer goes straight to the student, under “My questions”. You see their name, not their email address.`
              : 'Every question students sent an office or department because the chatbot couldn’t answer it. Each one waits in its own office’s or department’s dashboard; you can answer any of them, such as for an office with no account yet.'}
          </p>
        </div>
        <button type="button" className="link-button" onClick={load}>
          Refresh
        </button>
      </div>

      <div className="adm-filters">
        <div className="adm-chips" role="group" aria-label="Filter by status">
          {FILTERS.map(([key, label]) => (
            <button key={key} type="button" aria-pressed={filter === key} onClick={() => setFilter(key)}>
              {label} <span className="adm-chip-n">{counts[key]}</span>
            </button>
          ))}
          <button type="button" aria-pressed={filter === ''} onClick={() => setFilter('')}>
            All <span className="adm-chip-n">{tickets.length}</span>
          </button>
        </div>
      </div>

      {shown.length === 0 ? (
        <p className="voice-hint">
          {filter === 'open' ? 'Nothing waiting. New questions show up here.' : 'No questions here yet.'}
        </p>
      ) : (
        <ul className="ticket-list">
          {shown.map((t) => (
            <li key={t.ref} className={`ticket is-${t.status}`}>
              <div className="ticket-top">
                {t.status === 'answered' ? (
                  <span className="adm-pill is-ok">Answered</span>
                ) : t.closed ? (
                  <span className="adm-pill is-danger">Closed</span>
                ) : (
                  <span className="adm-pill is-wait">Waiting</span>
                )}
                <span className="ticket-meta">
                  {!office && `${t.office_name} · `}
                  {t.ref} · {when(t.created_at)}
                </span>
              </div>
              {canAnswer(t) ? (
                <button
                  type="button"
                  className="ticket-question adm-answer-pick"
                  aria-expanded={openRef === t.ref}
                  onClick={() => setOpenRef(openRef === t.ref ? null : t.ref)}
                >
                  {t.question}
                  {openRef !== t.ref && drafts[t.ref]?.trim() && <span className="adm-tag">Draft</span>}
                </button>
              ) : (
                <p className="ticket-question">{t.question}</p>
              )}
              <p className="ticket-meta">
                From {t.student_name ?? 'a deleted account'}
                {t.student_department && ` · ${t.student_department}`}
              </p>
              {t.answer && (
                <div className="ticket-answer">
                  <p className="ticket-answer-by">
                    {t.answered_by ?? t.office_name} · {when(t.answered_at)}
                  </p>
                  <p className="ticket-answer-text">{t.answer}</p>
                </div>
              )}
              {t.closed && t.status !== 'answered' && (
                <p className="voice-hint">The student’s account was deleted, so this can no longer be answered.</p>
              )}
              {canAnswer(t) && openRef === t.ref && (
                <AnswerForm
                  ticket={t}
                  token={token}
                  text={drafts[t.ref] ?? ''}
                  setText={(text) => setDrafts((prev) => ({ ...prev, [t.ref]: text }))}
                  onAnswered={(updated) => {
                    onAnswered(updated);
                    setOpenRef(null);
                  }}
                  onHide={() => setOpenRef(null)}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
