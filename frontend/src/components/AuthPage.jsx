import { useEffect, useState } from 'react';
import GoogleButton from './GoogleButton.jsx';
import ThemeToggle from './ThemeToggle.jsx';

// Three views, one URL each:
//   #/login  — the main door: Sign in with UB Mail (students and staff)
//   #/guest  — the side door: email + password for admins and guests
//   #/signup — guest sign-up
const VIEWS = { '#/guest': 'guest', '#/signup': 'signup' };

function viewFromHash() {
  return VIEWS[window.location.hash] ?? 'ubmail';
}

function go(view) {
  window.location.hash = { ubmail: '#/login', guest: '#/guest', signup: '#/signup' }[view];
}

export default function AuthPage({ auth, theme }) {
  const { config, login, signup, loginWithGoogle } = auth;
  const defaultPassword = config.default_password;
  const domain = config.google_domain || 'ub.edu.ph';

  const [view, setView] = useState(viewFromHash);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // New accounts start on the default password, so sign-up pre-fills it.
  useEffect(() => {
    setError(null);
    setPassword(view === 'signup' ? defaultPassword : '');
  }, [view, defaultPassword]);

  const run = async (action) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      window.history.replaceState(null, '', window.location.pathname);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (view === 'signup') run(() => signup(name.trim(), email.trim(), password));
    else run(() => login(email.trim(), password));
  };

  const errorBox = error && (
    <p className="auth-error" role="alert">
      {error}
    </p>
  );

  return (
    <div className="auth-shell">
      {/* Outside the form panel: its entrance animation would pin a fixed child to the panel. */}
      <ThemeToggle theme={theme.theme} onToggle={theme.toggle} className="auth-theme" />
      <aside className="cover" aria-hidden="true">
        <div className="cover-frame">
          <span className="cover-seal">UB</span>
          <p className="cover-kicker">University of Batangas</p>
          <p className="cover-title">
            UB{' '}
            <br />
            There
          </p>
          <p className="cover-line">
            Attendance, examinations, enrollment, conduct — ask in your own words and get the
            answer with its source.
          </p>
        </div>
      </aside>

      <section className="auth-sheet" aria-labelledby="auth-title">
        {view === 'ubmail' ? (
          <div className="auth-door">
            <p className="label">UB students &amp; staff</p>
            <h1 id="auth-title" className="auth-title">
              Sign in with your UB Mail.
            </h1>
            <p className="auth-lede">
              Use your @{domain} Google account — first time here, it makes your account for you.
            </p>

            <GoogleButton
              clientId={config.google_client_id}
              domain={domain}
              theme={theme.theme}
              mode="login"
              onCredential={(credential) => run(() => loginWithGoogle(credential))}
              onError={setError}
            />
            {errorBox}

            <div className="auth-side-door">
              <button type="button" className="link-button" onClick={() => go('guest')}>
                Admin / Guest login
              </button>
            </div>
          </div>
        ) : (
          <>
            <button type="button" className="link-button auth-back" onClick={() => go('ubmail')}>
              ← Back to UB Mail sign-in
            </button>

            <p className="label">{view === 'signup' ? 'Guests' : 'Admins & guests'}</p>
            <h1 id="auth-title" className="auth-title">
              {view === 'signup' ? 'Make a guest account.' : 'Log in with email.'}
            </h1>
            <p className="auth-lede">
              {view === 'signup'
                ? 'Any name and email address — both are required.'
                : 'For administrators and guests without UB Mail.'}
            </p>

            <form className="auth-form" onSubmit={handleSubmit}>
              {view === 'signup' && (
                <label className="auth-field">
                  <span>Name</span>
                  <input
                    type="text"
                    autoComplete="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    maxLength={80}
                  />
                </label>
              )}

              <label className="auth-field">
                <span>Email</span>
                <input
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </label>

              <label className="auth-field">
                <span>Password</span>
                <div className="auth-password">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    autoComplete={view === 'signup' ? 'new-password' : 'current-password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={view === 'signup' ? 8 : 1}
                  />
                  <button
                    type="button"
                    className="auth-reveal"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-pressed={showPassword}
                  >
                    {showPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
              </label>

              <p className="auth-hint">
                Every account starts with the password <code>{defaultPassword}</code>
                {view === 'signup' ? ' — you can change it after signing in.' : '.'}
              </p>

              {errorBox}

              <button type="submit" className="button-primary auth-submit" disabled={busy}>
                {busy ? 'Please wait…' : view === 'signup' ? 'Create guest account' : 'Log in'}
              </button>
            </form>

            <p className="auth-switch">
              {view === 'signup' ? 'Already have an account? ' : 'New guest? '}
              <button
                type="button"
                className="link-button"
                onClick={() => go(view === 'signup' ? 'guest' : 'signup')}
              >
                {view === 'signup' ? 'Log in' : 'Create a guest account'}
              </button>
            </p>
          </>
        )}
      </section>
    </div>
  );
}
