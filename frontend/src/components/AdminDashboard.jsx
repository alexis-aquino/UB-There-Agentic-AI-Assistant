import { useEffect, useMemo, useState } from 'react';
import { apiFetch } from '../api.js';
import AccountPanel from './AccountPanel.jsx';
import AdminDocuments from './AdminDocuments.jsx';
import {
  DailyChart,
  RangePicker,
  Stat,
  TopSources,
  UnansweredList,
  handbookRate,
  useReport,
} from './InquiryTrends.jsx';
import QueryLog from './QueryLog.jsx';
import { ROLE_NAMES } from '../roles.js';
import Masthead, { SubPage } from './Masthead.jsx';

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

function Overview({ token }) {
  const { days, setDays, report, error, load } = useReport('/api/admin/report', token);

  if (error) return <p className="voice-error">{error}</p>;
  if (!report) return <p className="voice-hint">Loading…</p>;

  const { inquiries, offices, accounts } = report;
  const rate = handbookRate(inquiries);
  const openTickets = offices.reduce((sum, o) => sum + o.open, 0);

  return (
    <>
      <RangePicker days={days} setDays={setDays} onRefresh={load} />

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
          <UnansweredList
            inquiries={inquiries}
            hint="Questions the handbook couldn’t answer, most-asked first — where it may need more content."
          />
        </section>

        <section>
          <TopSources inquiries={inquiries} />

          <h3>Offices</h3>
          <table className="dash-table">
            <thead>
              <tr>
                <th scope="col">Office</th>
                <th scope="col" className="num">
                  Waiting
                </th>
                <th scope="col" className="num">
                  Answered
                </th>
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
            {plural(accounts.guest, 'guest')} · {plural(accounts.student, 'student')} · {accounts.department} department
            staff · {plural(accounts.admin, 'administrator')}
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
        body: {
          role,
          office_id: role === 'department' ? officeId || null : null,
        },
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
          <select
            value={officeId}
            onChange={(e) => setOfficeId(e.target.value)}
            aria-label={`Office for ${person.name}`}
          >
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
        {['all', ...Object.keys(ROLE_NAMES)].map((r) => (
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
export default function AdminDashboard({ auth, theme }) {
  const { user, token, config, changePassword, logout } = auth;
  const [tab, setTab] = useState('overview');
  // A Menu page shown instead of the dashboard ('account'), or null.
  const [page, setPage] = useState(null);
  const [officeNames, setOfficeNames] = useState({});

  useEffect(() => {
    apiFetch('/api/offices')
      .then((data) => setOfficeNames(Object.fromEntries(data.offices.map((o) => [o.id, o.name]))))
      .catch(() => setOfficeNames({}));
  }, []);

  return (
    <div className="app-shell">
      <Masthead
        subtitle="Administration"
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
        <SubPage backLabel="Back to the dashboard" onBack={() => setPage(null)}>
          <AccountPanel user={user} defaultPassword={config.default_password} onChangePassword={changePassword} />
        </SubPage>
      )}

      <section className="voice-panel dash" aria-label="Administration" hidden={Boolean(page)}>
        <div className="dash-tabs" role="tablist">
          {[
            ['overview', 'Overview'],
            ['logs', 'Query logs'],
            ['accounts', 'Accounts'],
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
        {tab === 'overview' && <Overview token={token} />}
        {tab === 'logs' && (
          <QueryLog
            path="/api/admin/logs"
            token={token}
            hint="Every question students asked and every document they had checked. Photos are never kept."
          />
        )}
        {tab === 'accounts' && <Accounts token={token} selfId={user.id} />}
        {tab === 'documents' && <AdminDocuments token={token} officeNames={officeNames} />}
      </section>
    </div>
  );
}
