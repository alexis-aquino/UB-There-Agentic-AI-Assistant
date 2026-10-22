import { useRef, useState } from 'react';
import { DOC_TYPES, fileSize, loadKnowledge, newId, saveKnowledge } from '../admin/knowledge.js';
import { TOPICS } from '../admin/sampleData.js';
import { day } from '../admin/store.js';
import AdminPictures from './AdminPictures.jsx';

const BLANK = { title: '', topic: TOPICS[0], office: '', content: '' };

function StatusPill({ status }) {
  return status === 'indexed' ? (
    <span className="adm-pill is-ok">In the assistant</span>
  ) : (
    <span className="adm-pill is-wait">Waiting to be indexed</span>
  );
}

/** Add, change and remove what the assistant answers from: documents and short entries. */
export default function AdminKnowledge({ user }) {
  const [kb, setKb] = useState(loadKnowledge);
  const [editing, setEditing] = useState(null); // null, 'new', or an entry id
  const [draft, setDraft] = useState(BLANK);
  const [search, setSearch] = useState('');
  const [topic, setTopic] = useState('');
  const [open, setOpen] = useState(null);
  const [removing, setRemoving] = useState(null); // { kind, id, name } waiting for a yes
  const [uploadNote, setUploadNote] = useState('');
  const [storeFull, setStoreFull] = useState(false);
  const fileInput = useRef(null);

  function update(next) {
    setKb(next);
    // Pictures take room; if the browser can't keep them, say so instead of losing them quietly.
    setStoreFull(!saveKnowledge(next));
  }

  const waiting = [...kb.documents, ...kb.entries, ...kb.pictures].filter((x) => x.status === 'waiting').length;

  // ---- documents ----
  function addFiles(files) {
    const ok = [];
    const skipped = [];
    for (const f of files) {
      const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase();
      if (DOC_TYPES.includes(ext)) ok.push(f);
      else skipped.push(f.name);
    }
    const now = new Date().toISOString();
    const docs = ok.map((f) => ({
      id: newId('doc'),
      name: f.name,
      type: f.name.slice(f.name.lastIndexOf('.') + 1).toUpperCase(),
      size: f.size,
      addedAt: now,
      addedBy: user.name,
      status: 'waiting',
    }));
    if (docs.length) update({ ...kb, documents: [...docs, ...kb.documents] });
    setUploadNote(
      [
        docs.length && `Added ${docs.length} document${docs.length === 1 ? '' : 's'}.`,
        skipped.length && `Skipped ${skipped.join(', ')}: only ${DOC_TYPES.join(', ')} can be read.`,
      ]
        .filter(Boolean)
        .join(' '),
    );
  }

  // ---- entries ----
  function startNew() {
    setDraft(BLANK);
    setEditing('new');
  }

  function startEdit(entry) {
    setDraft({ title: entry.title, topic: entry.topic, office: entry.office, content: entry.content });
    setEditing(entry.id);
    setOpen(entry.id);
  }

  function saveEntry(e) {
    e.preventDefault();
    const clean = { ...draft, title: draft.title.trim(), office: draft.office.trim(), content: draft.content.trim() };
    if (!clean.title || !clean.content) return;
    const stamp = { updatedAt: new Date().toISOString(), updatedBy: user.name, status: 'waiting' };
    const entries =
      editing === 'new'
        ? [{ id: newId('entry'), ...clean, ...stamp }, ...kb.entries]
        : kb.entries.map((x) => (x.id === editing ? { ...x, ...clean, ...stamp } : x));
    update({ ...kb, entries });
    setEditing(null);
  }

  function remove() {
    const { kind, id } = removing;
    update({ ...kb, [kind]: kb[kind].filter((x) => x.id !== id) });
    setRemoving(null);
    if (editing === id) setEditing(null);
  }

  const text = search.trim().toLowerCase();
  const entries = kb.entries.filter(
    (x) =>
      (!topic || x.topic === topic) && (!text || `${x.title} ${x.content} ${x.office}`.toLowerCase().includes(text)),
  );

  const form = (
    <form className="adm-form" onSubmit={saveEntry}>
      <label>
        <span className="label">Title</span>
        <input
          type="text"
          value={draft.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          placeholder="e.g. Deadline for adding and dropping subjects"
          required
        />
      </label>
      <div className="adm-form-row">
        <label>
          <span className="label">Topic</span>
          <select value={draft.topic} onChange={(e) => setDraft({ ...draft, topic: e.target.value })}>
            {TOPICS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="label">Office (optional)</span>
          <input
            type="text"
            value={draft.office}
            onChange={(e) => setDraft({ ...draft, office: e.target.value })}
            placeholder="Who students can ask about it"
          />
        </label>
      </div>
      <label>
        <span className="label">Information</span>
        <textarea
          rows={6}
          value={draft.content}
          onChange={(e) => setDraft({ ...draft, content: e.target.value })}
          placeholder="Write it the way a student should be told it: dates, places, fees, steps."
          required
        />
      </label>
      <div className="adm-callout-actions">
        <button type="submit" className="chip-button" disabled={!draft.title.trim() || !draft.content.trim()}>
          {editing === 'new' ? 'Add to knowledge base' : 'Save changes'}
        </button>
        <button type="button" className="link-button" onClick={() => setEditing(null)}>
          Cancel
        </button>
      </div>
    </form>
  );

  return (
    <section className="adm-section adm-page" aria-labelledby="adm-kb-title">
      <div className="adm-tracker-head">
        <div>
          <h3 id="adm-kb-title">Knowledge base</h3>
          <p className="adm-sub">
            What the assistant answers from: documents such as the student handbook, short entries staff add for things
            that change, like office hours and deadlines, and pictures such as maps and forms.
          </p>
        </div>
      </div>

      {waiting > 0 && (
        <div className="adm-callout">
          <p>
            <strong>{waiting}</strong> {waiting === 1 ? 'change is' : 'changes are'} waiting to be indexed. The
            assistant uses them once the backend rebuilds its index.
          </p>
        </div>
      )}

      {storeFull && (
        <div className="adm-callout is-confirm" role="alert">
          <p>
            This browser is out of room, so the last change is kept only until the page is closed. Remove a picture or
            two to make space.
          </p>
        </div>
      )}

      {removing && (
        <div className="adm-callout is-confirm" role="alertdialog" aria-label="Confirm removal">
          <p>Remove “{removing.name}”? The assistant stops answering from it after the next index rebuild.</p>
          <div className="adm-callout-actions">
            <button type="button" className="adm-danger-button" onClick={remove}>
              Remove
            </button>
            <button type="button" className="link-button" onClick={() => setRemoving(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ---- entries ---- */}
      <div className="adm-kb-part">
        <div className="adm-year-switch">
          <h4 className="adm-heat-heading">Entries</h4>
          {editing !== 'new' && (
            <button type="button" className="chip-button" onClick={startNew}>
              + Add entry
            </button>
          )}
        </div>
        <p className="adm-sub">Short pieces of information, each about one thing.</p>

        {editing === 'new' && form}

        <div className="adm-filter-row adm-kb-filters">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search entries…"
            aria-label="Search entries"
          />
          <select value={topic} onChange={(e) => setTopic(e.target.value)} aria-label="Topic">
            <option value="">All topics</option>
            {TOPICS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>

        {entries.length === 0 ? (
          <p className="voice-hint">{kb.entries.length ? 'No entries match.' : 'No entries yet. Add the first one.'}</p>
        ) : (
          <ul className="adm-kb-list">
            {entries.map((x) => (
              <li key={x.id} className={open === x.id ? 'is-open' : ''}>
                <div className="adm-kb-head">
                  <button
                    type="button"
                    className="adm-log-question"
                    aria-expanded={open === x.id}
                    onClick={() => setOpen(open === x.id ? null : x.id)}
                  >
                    {x.title}
                  </button>
                  <StatusPill status={x.status} />
                </div>
                <p className="adm-log-ref">
                  {x.topic}
                  {x.office && ` · ${x.office}`} · updated {day(x.updatedAt)} by {x.updatedBy}
                </p>
                {open === x.id &&
                  (editing === x.id ? (
                    form
                  ) : (
                    <>
                      <p className="adm-kb-content">{x.content}</p>
                      <div className="adm-callout-actions">
                        <button type="button" className="link-button" onClick={() => startEdit(x)}>
                          Edit
                        </button>
                        <button
                          type="button"
                          className="link-button adm-danger-link"
                          onClick={() => setRemoving({ kind: 'entries', id: x.id, name: x.title })}
                        >
                          Remove
                        </button>
                      </div>
                    </>
                  ))}
              </li>
            ))}
          </ul>
        )}
      </div>

      <AdminPictures
        pictures={kb.pictures}
        user={user}
        StatusPill={StatusPill}
        onChange={(pictures) => update({ ...kb, pictures })}
        onRemove={(pic) => setRemoving({ kind: 'pictures', id: pic.id, name: pic.title })}
      />

      {/* ---- documents ---- */}
      <div className="adm-kb-part">
        <div className="adm-year-switch">
          <h4 className="adm-heat-heading">Documents</h4>
          <button type="button" className="chip-button" onClick={() => fileInput.current?.click()}>
            + Add document
          </button>
          <input
            ref={fileInput}
            type="file"
            accept={DOC_TYPES.join(',')}
            multiple
            hidden
            onChange={(e) => {
              addFiles([...e.target.files]);
              e.target.value = '';
            }}
          />
        </div>
        <p className="adm-sub">Whole files the assistant reads: {DOC_TYPES.join(', ')}.</p>
        {uploadNote && (
          <p className="adm-kb-note" role="status">
            {uploadNote}
          </p>
        )}

        {kb.documents.length === 0 ? (
          <p className="voice-hint">No documents yet.</p>
        ) : (
          <div className="adm-scroll">
            <table className="adm-log">
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Added</th>
                  <th scope="col">Status</th>
                  <th scope="col">
                    <span className="sr-only">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {kb.documents.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <span className="adm-account-name">{d.name}</span>
                      <span className="adm-log-ref">
                        {d.type} · {fileSize(d.size)}
                      </span>
                    </td>
                    <td className="adm-log-muted">
                      {day(d.addedAt)}
                      <span className="adm-log-ref">by {d.addedBy}</span>
                    </td>
                    <td>
                      <StatusPill status={d.status} />
                    </td>
                    <td className="adm-row-action">
                      <button
                        type="button"
                        className="link-button adm-danger-link"
                        onClick={() => setRemoving({ kind: 'documents', id: d.id, name: d.name })}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
