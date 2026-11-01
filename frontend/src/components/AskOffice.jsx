import { useEffect, useState } from 'react';
import { apiFetch } from '../api.js';

const GROUPS = [
  ['office', 'Offices'],
  ['department', 'Departments'],
];

/** Pass a question the assistant couldn't answer to a university office or department. It answers
 * in its dashboard; the app suggests the one that fits the question. */
export default function AskOffice({ question, inquiryId, token, onSent, onCancel }) {
  const [offices, setOffices] = useState([]);
  const [officeId, setOfficeId] = useState('');
  const [text, setText] = useState(question);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Signed in, so a student's own department can be suggested when no office fits.
    apiFetch(`/api/offices?question=${encodeURIComponent(question)}`, { token })
      .then((data) => {
        setOffices(data.offices);
        setOfficeId(data.suggested ?? data.offices[0]?.id ?? '');
      })
      .catch((err) => setError(err.message));
  }, [question, token]);

  const send = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const ticket = await apiFetch('/api/tickets', {
        token,
        body: { question: text.trim(), office_id: officeId, inquiry_id: inquiryId ?? null },
      });
      onSent(ticket);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <form className="ask-office" onSubmit={send}>
      <p className="ask-office-title">Ask an office or department</p>
      <label className="auth-field">
        <span>Send to</span>
        <select value={officeId} onChange={(e) => setOfficeId(e.target.value)} required>
          {GROUPS.map(([kind, label]) => (
            <optgroup key={kind} label={label}>
              {offices
                .filter((office) => office.kind === kind)
                .map((office) => (
                  <option key={office.id} value={office.id}>
                    {office.name}
                  </option>
                ))}
            </optgroup>
          ))}
        </select>
      </label>
      <label className="auth-field">
        <span>Your question</span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          maxLength={2000}
          required
        />
      </label>
      <p className="ask-office-note">
        They answer in UB There, and you’ll find it under “My questions”. They see your name, not
        your email address.
      </p>
      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}
      <div className="ask-office-actions">
        <button type="submit" className="button-primary" disabled={busy || !officeId || !text.trim()}>
          {busy ? 'Sending…' : 'Send question'}
        </button>
        <button type="button" className="link-button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
