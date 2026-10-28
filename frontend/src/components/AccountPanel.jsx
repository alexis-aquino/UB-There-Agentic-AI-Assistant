import { useState } from 'react';

const KINDS = { admin: 'Administrator', department: 'University department', student: 'Student', guest: 'Guest' };

/** Your own account: your name and password. Everyone has it — students and guests in the chat,
 * administrators and university departments in the dashboard. */
export default function AccountPanel({ user, defaultPassword, onChangePassword, onRename, onClose }) {
  const [name, setName] = useState(user.name);
  const [nameBusy, setNameBusy] = useState(false);
  const [nameError, setNameError] = useState(null);
  const [nameDone, setNameDone] = useState(false);
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

  const saveName = async (e) => {
    e.preventDefault();
    setNameBusy(true);
    setNameError(null);
    setNameDone(false);
    try {
      await onRename(name.trim());
      setNameDone(true);
    } catch (err) {
      setNameError(err.message);
    } finally {
      setNameBusy(false);
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
          <dd>{KINDS[user.account_type] ?? (user.guest ? 'Guest' : 'UB student / staff')}</dd>
        </div>
        {user.department && (
          <div>
            <dt>Department</dt>
            <dd>
              {user.department}
              {user.account_type === 'department' && ' · only an administrator can change it'}
            </dd>
          </div>
        )}
      </dl>

      {onRename && (
        <form className="account-form" onSubmit={saveName}>
          <h3>Your name</h3>
          <label className="auth-field">
            <span>{user.account_type === 'department' ? 'Name or office' : 'Full name'}</span>
            <input
              type="text"
              autoComplete="name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setNameDone(false);
              }}
              maxLength={80}
              required
            />
          </label>
          {nameError && (
            <p className="auth-error" role="alert">
              {nameError}
            </p>
          )}
          {nameDone && <p className="account-success">Name updated.</p>}
          <button type="submit" className="button-primary" disabled={nameBusy || !name.trim() || name.trim() === user.name}>
            {nameBusy ? 'Saving…' : 'Update name'}
          </button>
        </form>
      )}

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
