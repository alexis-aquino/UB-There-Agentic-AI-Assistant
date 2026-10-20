import { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../api.js';
import AccountPanel from './AccountPanel.jsx';
import AdminDocuments from './AdminDocuments.jsx';
import QueryLog from './QueryLog.jsx';
import {
  DailyChart,
  RangePicker,
  Stat,
  TopSources,
  UnansweredList,
  handbookRate,
  useReport,
} from './InquiryTrends.jsx';
import Masthead, { SubPage } from './Masthead.jsx';

const FILTERS = [
  { id: 'open', label: 'Waiting' },
  { id: 'answered', label: 'Answered' },
  { id: 'all', label: 'All' },
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

/** The answer box under one question. Saving again updates the answer the student sees. */
function ReplyForm({ ticket, token, staffName, onSaved, onCancel }) {
  const [text, setText] = useState(ticket.answer ?? '');
  const [answeredBy, setAnsweredBy] = useState(ticket.answered_by ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const saved = await apiFetch(`/api/department/tickets/${ticket.ref}/answer`, {
        token,
        body: { answer: text, answered_by: answeredBy },
      });
      onSaved(saved);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="ticket-reply" onSubmit={handleSubmit}>
      <label className="auth-field">
        <span>Your answer</span>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} maxLength={5000} required />
      </label>
      <label className="auth-field">
        <span>Shown to the student as</span>
        <input
          value={answeredBy}
          onChange={(e) => setAnsweredBy(e.target.value)}
          placeholder={staffName}
          maxLength={80}
        />
      </label>
      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}
      <div className="ask-office-actions">
        <button type="submit" className="button-primary" disabled={busy || !text.trim()}>
          {busy ? 'Sending…' : ticket.answer ? 'Update answer' : 'Send answer'}
        </button>
        {onCancel && (
          <button type="button" className="link-button" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

/** The handbook questions about this office (by its keywords), so staff see what students ask. */
function OfficeTrends({ token, officeName }) {
  const { days, setDays, report, error, load } = useReport('/api/department/report', token);

  if (error) return <p className="voice-error">{error}</p>;
  if (!report) return <p className="voice-hint">Loading…</p>;

  const { inquiries, tickets } = report;
  const rate = handbookRate(inquiries);

  return (
    <>
      <p className="voice-hint">
        Questions students asked the assistant that are about the {officeName ?? 'office'}, matched by the office’s
        keywords.
      </p>
      <RangePicker days={days} setDays={setDays} onRefresh={load} />

      <div className="stats">
        <Stat label="Questions asked" value={inquiries.asked} note={`last ${days} days`} />
        <Stat
          label="Answered by the handbook"
          value={rate === null ? '—' : `${rate}%`}
          note={`${inquiries.answered} of ${inquiries.asked}`}
        />
        <Stat label="Not in the handbook" value={inquiries.asked - inquiries.answered} note="see the list below" />
        <Stat label="Waiting for you" value={tickets.open} note={`${tickets.answered} answered, all time`} />
      </div>

      <DailyChart days={inquiries.per_day} />

      <div className="dash-columns">
        <section>
          <UnansweredList
            inquiries={inquiries}
            hint="Questions the handbook couldn’t answer, most-asked first — ones your office may want added to it."
          />
        </section>
        <section>
          <TopSources inquiries={inquiries} />
        </section>
      </div>
    </>
  );
}

/** For office staff: the questions students passed to their office, answered right here. */
export default function DepartmentDashboard({ auth, theme }) {
  const { user, token, config, changePassword, logout } = auth;
  const [tickets, setTickets] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('open');
  const [editing, setEditing] = useState(null);
  // A Menu page shown instead of the desk ('account'), or null.
  const [page, setPage] = useState(null);
  const [tab, setTab] = useState('questions');

  const load = useCallback(() => {
    setError(null);
    apiFetch('/api/department/tickets', { token })
      .then(setTickets)
      .catch((err) => setError(err.message));
  }, [token]);

  useEffect(load, [load]);

  const replace = (saved) => {
    setTickets((prev) => prev.map((t) => (t.ref === saved.ref ? saved : t)));
    setEditing(null);
  };

  const waiting = tickets?.filter((t) => t.status !== 'answered').length ?? 0;
  const shown =
    tickets?.filter((t) =>
      filter === 'all' ? true : filter === 'answered' ? t.status === 'answered' : t.status !== 'answered',
    ) ?? [];

  return (
    <div className="app-shell">
      <Masthead
        subtitle={`${user.office_name ?? 'Department'} · Questions desk`}
        menu={{
          user,
          onAccount: () => setPage('account'),
          theme: theme.theme,
          onToggleTheme: theme.toggle,
          onSignOut: logout,
        }}
      />

      {user.default_password && page !== 'account' && (
        <div className="notice" role="status">
          <span className="label">Notice</span>
          <span>You are still using the starting password. Change it to keep your account yours.</span>
          <button type="button" className="link-button" onClick={() => setPage('account')}>
            Change password
          </button>
        </div>
      )}

      {page === 'account' && (
        <SubPage backLabel="Back to the questions desk" onBack={() => setPage(null)}>
          <AccountPanel user={user} defaultPassword={config.default_password} onChangePassword={changePassword} />
        </SubPage>
      )}

      <section className="voice-panel dash" aria-label={user.office_name ?? 'Your office'} hidden={Boolean(page)}>
        <div className="dash-tabs" role="tablist">
          {[
            ['questions', 'Questions'],
            ['trends', 'Trends'],
            ['logs', 'Query logs'],
            ['documents', 'Documents'],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className="dash-tab"
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>
        {tab === 'trends' && <OfficeTrends token={token} officeName={user.office_name} />}
        {tab === 'logs' && (
          <QueryLog
            path="/api/department/logs"
            token={token}
            hint={`Questions and document checks about the ${user.office_name ?? 'office'}, matched by the office’s keywords.`}
          />
        )}
        {tab === 'documents' && (
          <>
            <p className="voice-hint">
              Your office’s documents in the assistant’s knowledge base. You can add files, and replace or delete the
              ones your office added. Other files are managed by their office or an admin.
            </p>
            <AdminDocuments token={token} base="/api/department/documents" />
          </>
        )}
        {tab === 'questions' && (
          <>
            <div className="voice-panel-head">
              <h2>{tickets ? `${waiting} waiting for an answer` : 'Questions for your office'}</h2>
              <button type="button" className="link-button" onClick={load}>
                Refresh
              </button>
            </div>
            <p className="voice-hint">
              Students sent these when the handbook didn’t have the answer. Your answer appears in their “My questions”,
              and students who signed in with UB Mail also get it by email.
            </p>

            <div className="dash-filters" role="group" aria-label="Show">
              {FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className="dash-filter"
                  aria-pressed={filter === f.id}
                  onClick={() => setFilter(f.id)}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {error && <p className="voice-error">{error}</p>}
            {!tickets && !error && <p className="voice-hint">Loading…</p>}
            {tickets && shown.length === 0 && (
              <p className="voice-hint">
                {filter === 'open' ? 'All caught up — no questions are waiting.' : 'Nothing here yet.'}
              </p>
            )}

            {shown.length > 0 && (
              <ul className="ticket-list">
                {shown.map((t) => (
                  <li key={t.ref} className={`ticket is-${t.status}`}>
                    <div className="ticket-top">
                      <span className={`ticket-status is-${t.status}`}>
                        {t.status === 'answered' ? 'Answered' : 'Waiting'}
                      </span>
                      <span className="ticket-meta">
                        {t.student_name} · {t.ref} · {when(t.created_at)}
                      </span>
                    </div>
                    <p className="ticket-question">{t.question}</p>

                    {t.status === 'answered' && editing !== t.ref ? (
                      <div className="ticket-answer">
                        <p className="ticket-answer-by">
                          {t.answered_by || t.office_name} · {when(t.answered_at)}
                        </p>
                        <p className="ticket-answer-text">{t.answer}</p>
                        <button type="button" className="link-button" onClick={() => setEditing(t.ref)}>
                          Edit answer
                        </button>
                      </div>
                    ) : (
                      <ReplyForm
                        key={`${t.ref}-${t.answered_at ?? 'new'}`}
                        ticket={t}
                        token={token}
                        staffName={user.name}
                        onSaved={replace}
                        onCancel={t.status === 'answered' ? () => setEditing(null) : null}
                      />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </div>
  );
}
