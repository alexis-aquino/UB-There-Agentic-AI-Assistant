import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch } from '../api.js';
import AccountPanel from './AccountPanel.jsx';
import ThemeToggle from './ThemeToggle.jsx';

const RANGES = [7, 14, 30];
const ROLE_NAMES = { student: 'Student', department: 'Department', admin: 'Admin' };

function shortDay(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function when(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

function Stat({ label, value, note }) {
  return (
    <div className="stat">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {note && <p className="stat-note">{note}</p>}
    </div>
  );
}

/** Questions per day: one series, so the title names it and no legend is needed. */
function DailyChart({ days }) {
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

function Overview({ token }) {
  const [days, setDays] = useState(14);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    apiFetch(`/api/admin/report?days=${days}`, { token })
      .then(setReport)
      .catch((err) => setError(err.message));
  }, [token, days]);

  useEffect(load, [load]);

  if (error) return <p className="voice-error">{error}</p>;
  if (!report) return <p className="voice-hint">Loading…</p>;

  const { inquiries, offices, accounts } = report;
  const rate = inquiries.asked ? Math.round((inquiries.answered / inquiries.asked) * 100) : null;
  const openTickets = offices.reduce((sum, o) => sum + o.open, 0);

  return (
    <>
      <div className="dash-filters" role="group" aria-label="Period">
        {RANGES.map((n) => (
          <button key={n} type="button" className="dash-filter" aria-pressed={days === n} onClick={() => setDays(n)}>
            Last {n} days
          </button>
        ))}
        <button type="button" className="link-button" onClick={load}>
          Refresh
        </button>
      </div>

      <div className="stats">
        <Stat label="Questions asked" value={inquiries.asked} note={`last ${days} days`} />
        <Stat
          label="Answered by the handbook"
          value={rate === null ? '—' : `${rate}%`}
          note={`${inquiries.answered} of ${inquiries.asked}`}
        />
        <Stat label="Not in the handbook" value={inquiries.asked - inquiries.answered} note="see the list below" />
        <Stat label="Waiting at offices" value={openTickets} note="all time" />
      </div>

      <DailyChart days={inquiries.per_day} />

      <div className="dash-columns">
        <section>
          <h3>Not in the handbook</h3>
          <p className="voice-hint">Questions the handbook couldn’t answer, most-asked first — where it may need more content.</p>
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
        </section>

        <section>
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

          <h3>Offices</h3>
          <table className="dash-table">
            <thead>
              <tr>
                <th scope="col">Office</th>
                <th scope="col" className="num">Waiting</th>
                <th scope="col" className="num">Answered</th>
              </tr>
            </thead>
            <tbody>
              {offices.map((o) => (
                <tr key={o.id}>
                  <td>{o.name}</td>
                  <td className="num">{o.open}</td>
                  <td className="num">{o.answered}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Accounts</h3>
          <p className="voice-hint">
            {plural(accounts.student, 'student')} · {accounts.department} department staff ·{' '}
            {plural(accounts.admin, 'admin')}
          </p>
        </section>
      </div>
    </>
  );
}

/** One account's row: change the role (and the office, for department staff) and save. */
function UserRow({ person, offices, token, isSelf, onSaved }) {
  const [role, setRole] = useState(person.role);
  const [officeId, setOfficeId] = useState(person.office_id ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const changed = role !== person.role || (role === 'department' && officeId !== (person.office_id ?? ''));

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const saved = await apiFetch(`/api/admin/users/${person.id}/role`, {
        token,
        method: 'PUT',
        body: { role, office_id: role === 'department' ? officeId || null : null },
      });
      onSaved(saved);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr>
      <td>
        {person.name}
        {isSelf && <span className="ticket-meta"> (you)</span>}
        <div className="ticket-meta">{person.email}</div>
      </td>
      <td>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          disabled={isSelf}
          aria-label={`Role for ${person.name}`}
        >
          {Object.entries(ROLE_NAMES).map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
        {role === 'department' && (
          <select value={officeId} onChange={(e) => setOfficeId(e.target.value)} aria-label={`Office for ${person.name}`}>
            <option value="">Choose an office…</option>
            {offices.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        )}
        {error && <p className="auth-error">{error}</p>}
      </td>
      <td className="num">
        {changed && (
          <button type="button" className="button-primary" onClick={save} disabled={busy}>
            {busy ? 'Saving…' : 'Save'}
          </button>
        )}
      </td>
    </tr>
  );
}

function Accounts({ token, selfId }) {
  const [people, setPeople] = useState(null);
  const [offices, setOffices] = useState([]);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');

  useEffect(() => {
    apiFetch('/api/admin/users', { token })
      .then(setPeople)
      .catch((err) => setError(err.message));
    apiFetch('/api/offices')
      .then((data) => setOffices(data.offices))
      .catch(() => setOffices([]));
  }, [token]);

  const shown = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (people ?? []).filter(
      (p) =>
        (roleFilter === 'all' || p.role === roleFilter) &&
        (!term || p.name.toLowerCase().includes(term) || p.email.toLowerCase().includes(term)),
    );
  }, [people, search, roleFilter]);

  if (error) return <p className="voice-error">{error}</p>;
  if (!people) return <p className="voice-hint">Loading…</p>;

  return (
    <>
      <div className="dash-filters" role="group" aria-label="Show">
        {['all', 'student', 'department', 'admin'].map((r) => (
          <button
            key={r}
            type="button"
            className="dash-filter"
            aria-pressed={roleFilter === r}
            onClick={() => setRoleFilter(r)}
          >
            {r === 'all' ? 'Everyone' : ROLE_NAMES[r]}
          </button>
        ))}
        <input
          className="dash-search"
          type="search"
          placeholder="Search name or email"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search accounts"
        />
      </div>
      <table className="dash-table dash-users">
        <thead>
          <tr>
            <th scope="col">Account</th>
            <th scope="col">Role</th>
            <th scope="col" />
          </tr>
        </thead>
        <tbody>
          {shown.map((p) => (
            <UserRow
              key={`${p.id}-${p.role}-${p.office_id}`}
              person={p}
              offices={offices}
              token={token}
              isSelf={p.id === selfId}
              onSaved={(saved) => setPeople((prev) => prev.map((x) => (x.id === saved.id ? saved : x)))}
            />
          ))}
        </tbody>
      </table>
      {shown.length === 0 && <p className="voice-hint">No accounts match.</p>}
    </>
  );
}

/** For administrators: inquiry trends, office workload, and who has which role. */
export default function AdminDashboard({ auth, theme, onOpenAssistant }) {
  const { user, token, config, changePassword, logout } = auth;
  const [tab, setTab] = useState('overview');
  const [showAccount, setShowAccount] = useState(false);

  return (
    <div className="app-shell">
      <header className="masthead">
        <div className="masthead-brand">
          <span className="seal" aria-hidden="true">UB</span>
          <div>
            <h1>UB There</h1>
            <p className="label">Administration</p>
          </div>
        </div>
        <nav className="masthead-nav" aria-label="Account">
          <button type="button" className="masthead-link" onClick={onOpenAssistant}>
            Open the assistant
          </button>
          <ThemeToggle theme={theme.theme} onToggle={theme.toggle} className="masthead-link" />
          <button
            type="button"
            className="masthead-link"
            aria-expanded={showAccount}
            onClick={() => setShowAccount((v) => !v)}
          >
            Account
          </button>
          <button type="button" className="masthead-link" onClick={logout}>
            Sign out
          </button>
        </nav>
      </header>

      {user.default_password && !showAccount && (
        <div className="notice" role="status">
          <span className="label">Notice</span>
          <span>You are still using the starting password. Change it to keep your account yours.</span>
          <button type="button" className="link-button" onClick={() => setShowAccount(true)}>
            Change password
          </button>
        </div>
      )}

      {showAccount && (
        <AccountPanel
          user={user}
          defaultPassword={config.default_password}
          onChangePassword={changePassword}
          onClose={() => setShowAccount(false)}
        />
      )}

      <section className="voice-panel dash" aria-label="Administration">
        <div className="dash-tabs" role="tablist">
          {[
            ['overview', 'Overview'],
            ['accounts', 'Accounts'],
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
        {tab === 'overview' ? <Overview token={token} /> : <Accounts token={token} selfId={user.id} />}
      </section>
    </div>
  );
}
