import { useRef, useState } from 'react';
import { IMAGE_TYPES, newId, shrinkImage } from '../admin/knowledge.js';
import { TOPICS } from '../admin/sampleData.js';
import { day } from '../admin/store.js';

const BLANK = { title: '', topic: TOPICS[0], description: '', src: '' };

/**
 * The knowledge base's pictures: campus maps, office locations, forms, schedules. The assistant
 * reads text only, so every picture needs a description of what it shows.
 */
export default function AdminPictures({ pictures, user, onChange, onRemove, StatusPill }) {
  const [editing, setEditing] = useState(null); // null, 'new', or a picture id
  const [draft, setDraft] = useState(BLANK);
  const [open, setOpen] = useState(null);
  const [note, setNote] = useState('');
  const fileInput = useRef(null);

  async function pick(file) {
    if (!file) return;
    if (!IMAGE_TYPES.includes(file.type)) {
      setNote(`${file.name} isn’t a picture the page can use. Use PNG, JPG, WebP or GIF.`);
      return;
    }
    try {
      const src = await shrinkImage(file);
      setNote('');
      // A new picture opens the form; changing an existing one keeps what was typed.
      if (editing && editing !== 'new') setDraft({ ...draft, src });
      else {
        setDraft({ ...BLANK, src, title: file.name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ') });
        setEditing('new');
      }
    } catch {
      setNote(`Couldn’t read ${file.name}. Try another picture.`);
    }
  }

  function startEdit(p) {
    setDraft({ title: p.title, topic: p.topic, description: p.description, src: p.src });
    setEditing(p.id);
    setOpen(p.id);
  }

  function save(e) {
    e.preventDefault();
    const clean = { ...draft, title: draft.title.trim(), description: draft.description.trim() };
    if (!clean.title || !clean.description || !clean.src) return;
    const stamp = { updatedAt: new Date().toISOString(), updatedBy: user.name, status: 'waiting' };
    onChange(
      editing === 'new'
        ? [{ id: newId('pic'), ...clean, ...stamp }, ...pictures]
        : pictures.map((p) => (p.id === editing ? { ...p, ...clean, ...stamp } : p)),
    );
    setEditing(null);
  }

  const form = (
    <form className="adm-form adm-pic-form" onSubmit={save}>
      <div className="adm-pic-preview">
        <img src={draft.src} alt="" />
        <button type="button" className="link-button" onClick={() => fileInput.current?.click()}>
          Change picture
        </button>
      </div>
      <div className="adm-pic-fields">
        <label>
          <span className="label">Title</span>
          <input
            type="text"
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            placeholder="e.g. Campus map, main building"
            required
          />
        </label>
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
          <span className="label">What the picture shows</span>
          <textarea
            rows={4}
            value={draft.description}
            onChange={(e) => setDraft({ ...draft, description: e.target.value })}
            placeholder="e.g. The Registrar is on the ground floor of the main building, beside the chapel entrance."
            required
          />
          <span className="adm-field-hint">
            The assistant reads this, not the picture, so write what a student needs to know from it.
          </span>
        </label>
        <div className="adm-callout-actions">
          <button
            type="submit"
            className="chip-button"
            disabled={!draft.title.trim() || !draft.description.trim() || !draft.src}
          >
            {editing === 'new' ? 'Add to knowledge base' : 'Save changes'}
          </button>
          <button type="button" className="link-button" onClick={() => setEditing(null)}>
            Cancel
          </button>
        </div>
      </div>
    </form>
  );

  return (
    <div className="adm-kb-part">
      <div className="adm-year-switch">
        <h4 className="adm-heat-heading">Pictures</h4>
        {editing !== 'new' && (
          <button type="button" className="chip-button" onClick={() => fileInput.current?.click()}>
            + Add picture
          </button>
        )}
        <input
          ref={fileInput}
          type="file"
          accept={IMAGE_TYPES.join(',')}
          hidden
          onChange={(e) => {
            pick(e.target.files[0]);
            e.target.value = '';
          }}
        />
      </div>
      <p className="adm-sub">Maps, office locations, forms and schedules, each with a description.</p>
      {note && (
        <p className="adm-kb-note" role="status">
          {note}
        </p>
      )}

      {editing === 'new' && form}

      {pictures.length === 0 && editing !== 'new' ? (
        <p className="voice-hint">No pictures yet.</p>
      ) : (
        <ul className="adm-pic-grid">
          {pictures.map((p) =>
            open === p.id ? (
              <li key={p.id} className="is-open">
                {editing === p.id ? (
                  form
                ) : (
                  <div className="adm-pic-detail">
                    <img src={p.src} alt={p.description} />
                    <div>
                      <div className="adm-kb-head">
                        <p className="adm-account-name">{p.title}</p>
                        <StatusPill status={p.status} />
                      </div>
                      <p className="adm-log-ref">
                        {p.topic} · updated {day(p.updatedAt)} by {p.updatedBy}
                      </p>
                      <p className="adm-kb-content">{p.description}</p>
                      <div className="adm-callout-actions">
                        <button type="button" className="link-button" onClick={() => startEdit(p)}>
                          Edit
                        </button>
                        <button type="button" className="link-button adm-danger-link" onClick={() => onRemove(p)}>
                          Remove
                        </button>
                        <button type="button" className="link-button" onClick={() => setOpen(null)}>
                          Close
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </li>
            ) : (
              <li key={p.id}>
                <button
                  type="button"
                  className="adm-pic-card"
                  onClick={() => setOpen(p.id)}
                  aria-label={`Open ${p.title}`}
                >
                  <img src={p.src} alt="" />
                  <span className="adm-pic-title">{p.title}</span>
                  <span className="adm-log-ref">{p.topic}</span>
                  {p.status === 'waiting' && <span className="adm-pill is-wait">Waiting</span>}
                </button>
              </li>
            ),
          )}
        </ul>
      )}
    </div>
  );
}
