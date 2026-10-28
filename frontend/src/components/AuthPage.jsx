import { useEffect, useState } from 'react';
import GoogleButton from './GoogleButton.jsx';
import ThemeToggle from './ThemeToggle.jsx';

// One sign-in page for every kind of account; the account decides where it lands.
// Three views, one URL each:
//   #/login  — the main door: Sign in with UB Mail (students, departments, administrators)
//   #/guest  — Login: email + password (guests, and the test accounts in STEPS TO RUN.md)
//   #/signup — guest sign-up
const VIEWS = { '#/guest': 'guest', '#/signup': 'signup' };

// Who can sign up with the form, and what each one gets.
const SIGNUP_TYPES = [
  ['student', 'Student', 'UB Mail and your department'],
  ['guest', 'Guest', 'Any email, no department'],
  ['department', 'University department', 'UB Mail; an administrator approves it'],
];

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
  const [accountType, setAccountType] = useState('student');
  const [department, setDepartment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // While Google sign-in is off, students and departments sign up here with their UB Mail and a
  // password. Once it's on, UB accounts come through Google, so this form is for guests only.
  const googleOn = Boolean(config.google_client_id);
  const types = SIGNUP_TYPES.filter(([key]) => !googleOn || key === 'guest');
  const chosen = types.some(([key]) => key === accountType) ? accountType : types[0][0];
  const needsDepartment = chosen !== 'guest';

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
    if (view === 'signup') {
      run(() => signup(name.trim(), email.trim(), password, chosen, needsDepartment ? department : null));
    }
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
            <p className="label">University of Batangas</p>
            <h1 id="auth-title" className="auth-title">
              Sign in to UB There.
            </h1>
            <p className="auth-lede">
              Students, university departments and administrators sign in with their @{domain} UB
              Mail. Guests without UB Mail use email.
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
                Login
              </button>
              <p className="auth-switch">
                No account yet?{' '}
                <button type="button" className="link-button" onClick={() => go('signup')}>
                  Sign up
                </button>
              </p>
            </div>
          </div>
        ) : (
          <>
            <button type="button" className="link-button auth-back" onClick={() => go('ubmail')}>
              ← Back to UB Mail sign-in
            </button>

            <p className="label">
              {view === 'signup' ? 'New account' : 'Login'}
            </p>
            <h1 id="auth-title" className="auth-title">
              {view === 'signup' ? 'Create your account.' : 'Log in with email.'}
            </h1>
            <p className="auth-lede">
              {view === 'signup'
                ? googleOn
                  ? `Guests sign up here. Students and university departments use the UB Mail button.`
                  : `Students and university departments use their @${domain} UB Mail; guests can use any email.`
                : 'Your account type comes from your account.'}
            </p>

            <form className="auth-form" onSubmit={handleSubmit}>
              {view === 'signup' && types.length > 1 && (
                <fieldset className="auth-types">
                  <legend>I am a</legend>
                  {types.map(([key, label, note]) => (
                    <label key={key} className={chosen === key ? 'is-on' : ''}>
                      <input
                        type="radio"
                        name="account-type"
                        value={key}
                        checked={chosen === key}
                        onChange={() => setAccountType(key)}
                      />
                      <strong>{label}</strong>
                      <span>{note}</span>
                    </label>
                  ))}
                </fieldset>
              )}

              {view === 'signup' && (
                <label className="auth-field">
                  <span>{chosen === 'department' ? 'Name or office' : 'Full name'}</span>
                  <input
                    type="text"
                    autoComplete="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={chosen === 'department' ? 'e.g. CIT Dean’s Office' : 'e.g. Juan Dela Cruz'}
                    required
                    maxLength={80}
                  />
                </label>
              )}

              <label className="auth-field">
                <span>{view === 'signup' && needsDepartment ? 'UB Mail' : 'Email'}</span>
                <input
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={view === 'signup' && needsDepartment ? `name@${domain}` : undefined}
                  required
                />
              </label>

              {view === 'signup' && needsDepartment && (
                <label className="auth-field">
                  <span>Department</span>
                  <select value={department} onChange={(e) => setDepartment(e.target.value)} required>
                    <option value="">Choose your department…</option>
                    {(config.departments ?? []).map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {view === 'signup' && chosen === 'department' && (
                <p className="auth-hint">
                  An administrator approves department accounts before they can see any student’s questions.
                </p>
              )}

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
                {busy ? 'Please wait…' : view === 'signup' ? 'Create account' : 'Log in'}
              </button>
            </form>

            {/* The login page is only for logging in; sign-up is on the main page. */}
            {view === 'signup' && (
              <p className="auth-switch">
                Already have an account?{' '}
                <button type="button" className="link-button" onClick={() => go('guest')}>
                  Login
                </button>
              </p>
            )}
          </>
        )}
      </section>
    </div>
  );
}
