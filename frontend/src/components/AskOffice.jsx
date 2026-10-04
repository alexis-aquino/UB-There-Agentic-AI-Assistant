import { useEffect, useState } from 'react';
import { apiFetch } from '../api.js';

/** Pass a question the assistant couldn't answer to a university office. */
export default function AskOffice({ question, token, onSent, onCancel }) {
  const [offices, setOffices] = useState([]);
  const [officeId, setOfficeId] = useState('');
  const [text, setText] = useState(question);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiFetch(`/api/offices?question=${encodeURIComponent(question)}`)
      .then((data) => {
        setOffices(data.offices);
        setOfficeId(data.suggested ?? data.offices[0]?.id ?? '');
      })
      .catch((err) => setError(err.message));
  }, [question]);

  const send = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const ticket = await apiFetch('/api/tickets', {
        token,
        body: { question: text.trim(), office_id: officeId },
      });
      onSent(ticket);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <form className="ask-office" onSubmit={send}>
      <p className="ask-office-title">Ask an office</p>
      <label className="auth-field">
        <span>Send to</span>
        <select value={officeId} onChange={(e) => setOfficeId(e.target.value)} required>
          {offices.map((office) => (
            <option key={office.id} value={office.id}>
              {office.name}
            </option>
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
        The office answers in UB There, under “My questions”. Your email address isn’t shared
        with them.
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
