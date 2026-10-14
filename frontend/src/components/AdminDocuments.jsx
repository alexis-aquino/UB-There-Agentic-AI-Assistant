import { useCallback, useEffect, useRef, useState } from 'react';
import { API_URL, apiFetch } from '../api.js';

const STATUS = {
  indexed: { label: 'In the index', className: 'is-answered' },
  changed: { label: 'Changed — rebuild to use', className: 'is-open' },
  new: { label: 'New — rebuild to use', className: 'is-open' },
  removed: { label: 'Deleted — rebuild to drop', className: 'is-open' },
};

const ACTIONS = {
  added: 'Added',
  replaced: 'Replaced',
  deleted: 'Deleted',
  'rebuild started': 'Rebuild started',
  'rebuild finished': 'Rebuild finished',
  'rebuild failed': 'Rebuild failed',
};

function when(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function size(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Document audit (DFD 4.0): the handbook files, whether the index has them, and who changed what. */
export default function AdminDocuments({ token }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  const load = useCallback(() => {
    apiFetch('/api/admin/documents', { token })
      .then((body) => {
        setData(body);
        setError(null);
      })
      .catch((err) => setError(err.message));
  }, [token]);

  useEffect(load, [load]);

  // While a rebuild runs, check on it every few seconds.
  const running = data?.rebuild.state === 'running';
  useEffect(() => {
    if (!running) return undefined;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [running, load]);

  const upload = async (files) => {
    setBusy(true);
    setNotice(null);
    setError(null);
    const done = [];
    try {
      for (const file of files) {
        const existing = data.documents.find((d) => d.name === file.name && d.status !== 'removed');
        if (existing && !window.confirm(`Replace ${file.name}? The old version is not kept.`)) continue;
        const form = new FormData();
        form.append('file', file);
        // Not apiFetch: that sends JSON, and an upload is a form.
        const res = await fetch(`${API_URL}/api/admin/documents`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(`${file.name}: ${body.detail ?? `upload failed (${res.status})`}`);
        done.push(file.name);
      }
      if (done.length) setNotice(`Saved ${done.join(', ')}. Rebuild the index so the assistant uses it.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
      load();
    }
  };

  const remove = async (name) => {
    if (!window.confirm(`Delete ${name}? This can't be undone.`)) return;
    setNotice(null);
    setError(null);
    try {
      await apiFetch(`/api/admin/documents/${encodeURIComponent(name)}`, { token, method: 'DELETE' });
      setNotice(`Deleted ${name}. Rebuild the index so the assistant stops using it.`);
    } catch (err) {
      setError(err.message);
    }
    load();
  };

  const rebuild = async () => {
    setNotice(null);
    setError(null);
    try {
      await apiFetch('/api/admin/documents/rebuild', { token, method: 'POST' });
    } catch (err) {
      setError(err.message);
    }
    load();
  };

  if (!data) return error ? <p className="voice-error">{error}</p> : <p className="voice-hint">Loading…</p>;

  const { documents, rebuild: state, events } = data;
  const pending = documents.filter((d) => d.status !== 'indexed').length;

  return (
    <>
      <div className="docs-status">
        <div>
          <p className="stat-label">Search index</p>
          <p className="docs-status-line">
            {running
              ? 'Rebuilding now — the assistant pauses until it’s done.'
              : !data.has_manifest
                ? 'Built before document tracking. Rebuild once to start tracking changes.'
                : data.up_to_date
                  ? `Up to date · built ${when(data.built_at)}`
                  : `${pending} change${pending === 1 ? '' : 's'} not in the index yet · built ${when(data.built_at)}`}
          </p>
          {state.state === 'done' && !running && <p className="stat-note">Last rebuild: {state.message}</p>}
          {state.state === 'failed' && (
            <p className="auth-error" role="alert">
              Last rebuild failed: {state.message}
            </p>
          )}
        </div>
        <button type="button" className="button-primary" onClick={rebuild} disabled={running || busy}>
          {running ? 'Rebuilding…' : 'Rebuild index'}
        </button>
      </div>

      <div className="docs-upload">
        <label className="link-button docs-upload-button">
          {busy ? 'Uploading…' : 'Add or replace documents'}
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={data.supported.join(',')}
            disabled={busy || running}
            onChange={(e) => e.target.files.length && upload([...e.target.files])}
          />
        </label>
        <span className="ticket-meta">
          {data.supported.join(', ')} · up to {data.max_upload_mb} MB each
        </span>
      </div>

      {notice && (
        <p className="ask-office-sent" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}

      {documents.length === 0 ? (
        <p className="voice-hint">No documents yet. Add the student handbook to get started.</p>
      ) : (
        <table className="dash-table dash-docs">
          <thead>
            <tr>
              <th scope="col">Document</th>
              <th scope="col">Status</th>
              <th scope="col" className="num">Passages</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.name}>
                <td>
                  {d.name}
                  <div className="ticket-meta">
                    {size(d.size)}
                    {d.modified && ` · changed ${when(d.modified)}`}
                    {d.pages != null && ` · ${d.pages} page${d.pages === 1 ? '' : 's'}`}
                  </div>
                </td>
                <td>
                  <span className={`ticket-status ${(STATUS[d.status] ?? STATUS.new).className}`}>
                    {(STATUS[d.status] ?? STATUS.new).label}
                  </span>
                </td>
                <td className="num">
                  {d.passages ?? '—'}
                  {d.passages != null && <span className="docs-phone-only"> passage{d.passages === 1 ? '' : 's'}</span>}
                </td>
                <td className="num">
                  {d.status !== 'removed' && (
                    <button type="button" className="link-button" onClick={() => remove(d.name)} disabled={running}>
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3>Change log</h3>
      {events.length === 0 ? (
        <p className="voice-hint">No changes yet.</p>
      ) : (
        <table className="dash-table">
          <tbody>
            {events.map((e, i) => (
              <tr key={i}>
                <td className="docs-when">{when(e.at)}</td>
                <td>
                  <strong>{ACTIONS[e.action] ?? e.action}</strong>
                  {e.file && ` · ${e.file}`}
                  {e.detail && <div className="ticket-meta">{e.detail}</div>}
                </td>
                <td className="ticket-meta">{e.actor}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
