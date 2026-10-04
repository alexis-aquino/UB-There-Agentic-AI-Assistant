import { useState } from 'react';

export default function AccountPanel({ user, defaultPassword, onChangePassword, onClose }) {
  const [current, setCurrent] = useState(user.default_password ? defaultPassword : '');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (next !== confirm) {
      setError('The new passwords do not match.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onChangePassword(current, next);
      setDone(true);
      setNext('');
      setConfirm('');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="voice-panel" aria-label="Account">
      <div className="voice-panel-head">
        <h2>Account</h2>
        <button type="button" className="link-button" onClick={onClose}>
          Close
        </button>
      </div>

      <dl className="voice-facts">
        <div>
          <dt>Signed in as</dt>
          <dd>
            {user.name} · {user.email}
          </dd>
        </div>
        <div>
          <dt>Account type</dt>
          <dd>{user.guest ? 'Guest' : 'UB student / staff'}</dd>
        </div>
      </dl>

      <form className="account-form" onSubmit={handleSubmit}>
        <h3>Change password</h3>
        <label className="auth-field">
          <span>Current password</span>
          <input
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
          />
        </label>
        <label className="auth-field">
          <span>New password</span>
          <input
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            minLength={8}
            required
          />
        </label>
        <label className="auth-field">
          <span>Confirm new password</span>
          <input
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            minLength={8}
            required
          />
        </label>
        {error && (
          <p className="auth-error" role="alert">
            {error}
          </p>
        )}
        {done && <p className="account-success">Password updated.</p>}
        <button type="submit" className="button-primary" disabled={busy}>
          {busy ? 'Saving…' : 'Update password'}
        </button>
      </form>
    </section>
  );
}
