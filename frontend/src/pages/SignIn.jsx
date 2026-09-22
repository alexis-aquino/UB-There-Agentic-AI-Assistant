import { useEffect, useState } from 'react';
import { api } from '../api.js';
import '../components/ChatBot.css';

/**
 * Three ways in, matching the paper's two student audiences plus staff:
 * guests (prospective students) give a name and email; current students use their
 * UB address; admins use the separate staff login.
 */
export default function SignIn({ onUser, onAdmin }) {
  const [mode, setMode] = useState('guest');
  const [config, setConfig] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const [guestName, setGuestName] = useState('');
  const [guestEmail, setGuestEmail] = useState('');

  const [studentMode, setStudentMode] = useState('login');
  const [studentName, setStudentName] = useState('');
  const [studentEmail, setStudentEmail] = useState('');
  const [studentNumber, setStudentNumber] = useState('');
  const [password, setPassword] = useState('');

  const [adminUser, setAdminUser] = useState('');
  const [adminPass, setAdminPass] = useState('');

  useEffect(() => {
    api.authConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  const domain = config?.student_email_domain ?? 'ub.edu.ph';

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const submitGuest = (e) => {
    e.preventDefault();
    run(async () => onUser(await api.guestSignIn(guestName, guestEmail)));
  };

  const submitStudent = (e) => {
    e.preventDefault();
    run(async () => {
      const result =
        studentMode === 'register'
          ? await api.studentRegister({
              full_name: studentName,
              email: studentEmail,
              password,
              student_number: studentNumber,
            })
          : await api.studentLogin(studentEmail, password);
      onUser(result);
    });
  };

  const submitAdmin = (e) => {
    e.preventDefault();
    run(async () => onAdmin(await api.adminLogin(adminUser, adminPass)));
  };

  return (
    <div className="signin-page">
      <div className="signin-card">
        <header className="signin-head">
          <span className="brand-mark" aria-hidden="true">UB</span>
          <div>
            <h1>UB There</h1>
            <p>University of Batangas · Student Assistant</p>
          </div>
        </header>

        <div className="signin-tabs" role="tablist">
          {[
            ['guest', 'Guest'],
            ['student', 'Current student'],
            ['admin', 'Staff'],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={mode === key}
              className={`signin-tab ${mode === key ? 'is-active' : ''}`}
              onClick={() => {
                setMode(key);
                setError(null);
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === 'guest' && (
          <form className="signin-form" onSubmit={submitGuest}>
            <p className="signin-hint">
              Thinking of applying? Just tell us who you are — no password needed. You can ask
              about admission requirements, tuition, entrance exams and courses.
            </p>
            <label>
              Full name
              <input
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                placeholder="Juan dela Cruz"
                autoComplete="name"
                required
              />
            </label>
            <label>
              Email address
              <input
                type="email"
                value={guestEmail}
                onChange={(e) => setGuestEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </label>
            <button className="button-primary" disabled={busy}>
              {busy ? 'Please wait…' : 'Continue as guest'}
            </button>
          </form>
        )}

        {mode === 'student' && (
          <form className="signin-form" onSubmit={submitStudent}>
            <div className="signin-switch">
              <button
                type="button"
                className={studentMode === 'login' ? 'is-active' : ''}
                onClick={() => setStudentMode('login')}
              >
                Sign in
              </button>
              <button
                type="button"
                className={studentMode === 'register' ? 'is-active' : ''}
                onClick={() => setStudentMode('register')}
              >
                Register
              </button>
            </div>

            <p className="signin-hint">
              Current students sign in with their <strong>@{domain}</strong> address. This unlocks
              document auditing and inquiry tracking.
            </p>

            {studentMode === 'register' && (
              <>
                <label>
                  Full name
                  <input
                    value={studentName}
                    onChange={(e) => setStudentName(e.target.value)}
                    autoComplete="name"
                    required
                  />
                </label>
                <label>
                  Student number <span className="optional">(optional)</span>
                  <input
                    value={studentNumber}
                    onChange={(e) => setStudentNumber(e.target.value)}
                    placeholder="21-01234"
                  />
                </label>
              </>
            )}

            <label>
              UB email
              <input
                type="email"
                value={studentEmail}
                onChange={(e) => setStudentEmail(e.target.value)}
                placeholder={`yourname@${domain}`}
                autoComplete="email"
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={studentMode === 'register' ? 'new-password' : 'current-password'}
                required
              />
            </label>
            {studentMode === 'register' && (
              <p className="signin-note">At least 8 characters.</p>
            )}

            <button className="button-primary" disabled={busy}>
              {busy ? 'Please wait…' : studentMode === 'register' ? 'Create account' : 'Sign in'}
            </button>

            {config?.google_enabled ? (
              <p className="signin-note">Sign in with Google is available on this server.</p>
            ) : (
              <p className="signin-note">
                UB mail runs on Google Workspace, so Sign in with Google can replace this
                password once an OAuth client ID is configured.
              </p>
            )}
          </form>
        )}

        {mode === 'admin' && (
          <form className="signin-form" onSubmit={submitAdmin}>
            <p className="signin-hint">
              For university staff. Manage the knowledge base, review inquiries and handle
              escalated questions.
            </p>
            <label>
              Username
              <input
                value={adminUser}
                onChange={(e) => setAdminUser(e.target.value)}
                autoComplete="username"
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={adminPass}
                onChange={(e) => setAdminPass(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <button className="button-primary" disabled={busy}>
              {busy ? 'Please wait…' : 'Sign in to dashboard'}
            </button>
          </form>
        )}

        {error && <p className="signin-error">{error}</p>}
      </div>
    </div>
  );
}
