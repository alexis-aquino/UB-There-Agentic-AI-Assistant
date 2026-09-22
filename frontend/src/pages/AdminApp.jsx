import { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';
import '../components/ChatBot.css';

const STATUSES = ['new', 'sent', 'acknowledged', 'resolved'];

export default function AdminApp({ admin, onSignOut }) {
  const [tab, setTab] = useState('overview');
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  const token = admin.access_token;

  const loadStats = useCallback(() => {
    api.adminStats(token).then(setStats).catch((e) => setError(e.message));
  }, [token]);

  useEffect(loadStats, [loadStats]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">UB</span>
          <div>
            <h1>UB There — Dashboard</h1>
            <p>
              {admin.username}
              <span className="badge">{admin.role.replace('_', ' ')}</span>
              {admin.department && <span className="badge">{admin.department}</span>}
            </p>
          </div>
        </div>
        <nav className="header-actions">
          {[
            ['overview', 'Overview'],
            ['escalations', 'Escalations'],
            ['inquiries', 'Inquiries'],
            ['documents', 'Knowledge base'],
            ['departments', 'Departments'],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`chip-button ${tab === key ? 'is-on' : ''}`}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
          <button type="button" className="chip-button" onClick={onSignOut}>
            Sign out
          </button>
        </nav>
      </header>

      <main className="panel-page">
        {error && <p className="chat-error">{error}</p>}
        {tab === 'overview' && <Overview stats={stats} />}
        {tab === 'escalations' && <Escalations token={token} onChange={loadStats} />}
        {tab === 'inquiries' && <Inquiries token={token} />}
        {tab === 'documents' && (
          <Documents token={token} isSuper={admin.role === 'superadmin'} onChange={loadStats} />
        )}
        {tab === 'departments' && (
          <Departments token={token} isSuper={admin.role === 'superadmin'} />
        )}
      </main>
    </div>
  );
}

function Overview({ stats }) {
  if (!stats) return <section className="panel">Loading…</section>;

  return (
    <section className="panel">
      <h2>Overview</h2>
      <div className="stat-grid">
        {[
          ['Questions asked', stats.inquiries],
          ['Escalations', stats.escalations],
          ['Still open', stats.open_escalations],
          ['Documents indexed', stats.documents],
        ].map(([label, value]) => (
          <div key={label} className="stat-tile">
            <span className="stat-value">{value}</span>
            <span className="stat-label">{label}</span>
          </div>
        ))}
      </div>

      <dl className="track-facts">
        <div>
          <dt>Answer model</dt>
          <dd>{stats.provider}</dd>
        </div>
        <div>
          <dt>Escalation threshold</dt>
          <dd>{stats.confidence_threshold}</dd>
        </div>
        <div>
          <dt>Email mode</dt>
          <dd>
            {stats.mail_mode === 'live' ? (
              <span className="chip">LIVE — emails are being sent</span>
            ) : (
              <span className="chip chip-muted">
                Dry run — escalations recorded, nothing sent
              </span>
            )}
          </dd>
        </div>
      </dl>
    </section>
  );
}

function Escalations({ token, onChange }) {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    api.adminEscalations(token).then(setRows).catch((e) => setError(e.message));
  }, [token]);

  useEffect(load, [load]);

  const update = async (id, payload) => {
    try {
      await api.adminUpdateEscalation(token, id, payload);
      load();
      onChange?.();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section className="panel">
      <h2>Escalated inquiries</h2>
      <p className="panel-hint">
        Questions the assistant could not answer from official documents, routed to the
        responsible office.
      </p>
      {error && <p className="chat-error">{error}</p>}
      {rows.length === 0 && <p className="panel-hint">No escalations yet.</p>}

      <div className="row-list">
        {rows.map((row) => (
          <article key={row.id} className="row-card">
            <div className="row-head">
              <code>{row.reference_code}</code>
              <span className="chip">{row.department_name ?? 'Unassigned'}</span>
              {!row.delivered && row.delivery_mode === 'dry_run' && (
                <span className="chip chip-muted">not sent (dry run)</span>
              )}
              <select
                value={row.status}
                onChange={(e) => update(row.id, { status: e.target.value })}
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <p className="row-question">{row.question}</p>
            <p className="row-meta">
              {row.student_email || 'no contact given'} · confidence{' '}
              {Math.round(row.confidence * 100)}% · {row.routing_reason}
            </p>

            <button
              type="button"
              className="link-button"
              onClick={() => setOpen(open === row.id ? null : row.id)}
            >
              {open === row.id ? 'Hide details' : 'View email & notes'}
            </button>

            {open === row.id && (
              <div className="row-details">
                <pre>{row.rendered_email}</pre>
                <label>
                  Resolution note (visible to the student)
                  <textarea
                    defaultValue={row.resolution_note}
                    rows={3}
                    onBlur={(e) =>
                      e.target.value !== row.resolution_note &&
                      update(row.id, { resolution_note: e.target.value })
                    }
                  />
                </label>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function Inquiries({ token }) {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    api.adminInquiries(token).then(setRows).catch(() => setRows([]));
  }, [token]);

  return (
    <section className="panel">
      <h2>All questions asked</h2>
      <p className="panel-hint">Useful for spotting what students repeatedly need.</p>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Question</th>
              <th>Confidence</th>
              <th>Escalated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td>{r.question}</td>
                <td>{Math.round(r.confidence * 100)}%</td>
                <td>{r.escalated ? 'yes' : 'no'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <p className="panel-hint">No questions logged yet.</p>}
    </section>
  );
}

function Documents({ token, isSuper, onChange }) {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    api.adminDocuments(token).then(setRows).catch((e) => setError(e.message));
  }, [token]);

  useEffect(load, [load]);

  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.adminUploadDocument(token, file);
      setMessage(`Uploaded ${file.name}. Re-index to make it searchable.`);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      event.target.value = '';
    }
  };

  const reindex = async () => {
    setBusy(true);
    setError(null);
    setMessage('Re-indexing… this can take a minute.');
    try {
      const result = await api.adminReindex(token);
      setMessage(`Indexed ${result.chunks} chunks from ${result.files.length} file(s).`);
      load();
      onChange?.();
    } catch (e) {
      setError(e.message);
      setMessage(null);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id, name) => {
    if (!window.confirm(`Delete "${name}" from the knowledge base?`)) return;
    try {
      await api.adminDeleteDocument(token, id);
      setMessage(`Deleted ${name}. Re-index to apply.`);
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section className="panel">
      <h2>Knowledge base</h2>
      <p className="panel-hint">
        The official documents the assistant answers from. Changes only take effect after
        re-indexing.
      </p>

      {isSuper && (
        <div className="panel-actions">
          <label className="file-drop is-inline">
            <input type="file" onChange={upload} disabled={busy} />
            <span>{busy ? 'Working…' : 'Upload document'}</span>
          </label>
          <button type="button" className="button-primary" onClick={reindex} disabled={busy}>
            Re-index
          </button>
        </div>
      )}

      {message && <p className="panel-message">{message}</p>}
      {error && <p className="chat-error">{error}</p>}

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>File</th>
              <th>Size</th>
              <th>Indexed</th>
              {isSuper && <th />}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.filename}</td>
                <td>{(r.size_bytes / 1024).toFixed(0)} KB</td>
                <td>{r.indexed_at ? new Date(r.indexed_at).toLocaleString() : 'not yet'}</td>
                {isSuper && (
                  <td>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => remove(r.id, r.filename)}
                    >
                      Delete
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && (
        <p className="panel-hint">
          No documents recorded. Upload one, or re-index to pick up files already in the folder.
        </p>
      )}
    </section>
  );
}

function Departments({ token, isSuper }) {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(null);

  const load = useCallback(() => {
    api.adminDepartments(token).then(setRows).catch((e) => setError(e.message));
  }, [token]);

  useEffect(load, [load]);

  const save = async (id, payload) => {
    try {
      await api.adminUpdateDepartment(token, id, payload);
      setSaved(id);
      setError(null);
      load();
      window.setTimeout(() => setSaved(null), 2000);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section className="panel">
      <h2>Departments</h2>
      <p className="panel-hint">
        Where escalated inquiries are sent, and the keywords used to route them. The seeded
        addresses are <strong>placeholders</strong> — replace them with real office addresses
        before switching email to live.
      </p>
      {error && <p className="chat-error">{error}</p>}

      <div className="row-list">
        {rows.map((row) => (
          <article key={row.id} className="row-card">
            <div className="row-head">
              <strong>{row.name}</strong>
              {row.is_fallback && <span className="chip chip-muted">fallback</span>}
              {saved === row.id && <span className="chip">saved</span>}
            </div>
            <label>
              Email
              <input
                defaultValue={row.email}
                disabled={!isSuper}
                onBlur={(e) => e.target.value !== row.email && save(row.id, { email: e.target.value })}
              />
            </label>
            <label>
              Routing keywords (comma separated)
              <textarea
                defaultValue={row.keywords}
                rows={2}
                disabled={!isSuper}
                onBlur={(e) =>
                  e.target.value !== row.keywords && save(row.id, { keywords: e.target.value })
                }
              />
            </label>
          </article>
        ))}
      </div>
      {!isSuper && <p className="panel-hint">Only a superadmin can change these.</p>}
    </section>
  );
}
