import AdminDashboard from './components/AdminDashboard.jsx';
import AuthPage from './components/AuthPage.jsx';
import ChatBot from './components/ChatBot.jsx';
import useAuth from './hooks/useAuth.js';
import useTheme from './hooks/useTheme.js';

function AwaitingApproval({ user, onSignOut }) {
  return (
    <div className="app-shell">
      <header className="masthead">
        <div className="masthead-brand">
          <span className="seal" aria-hidden="true">
            UB
          </span>
          <div>
            <h1>UB There</h1>
            <p className="label">University department · {user.department}</p>
          </div>
        </div>
        <button type="button" className="chip-button" onClick={onSignOut}>
          Sign out
        </button>
      </header>
      <main className="page">
        <section className="page-cover">
          <p className="label">Waiting for approval</p>
          <h2 className="page-title">
            Almost <em>there.</em>
          </h2>
          <p className="page-lede">
            Your account for the {user.department} is set up. An administrator needs to approve it before you can
            see your department’s students and their questions. Sign in again once they have.
          </p>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  const auth = useAuth();
  const theme = useTheme();

  if (auth.status === 'loading') return <div className="auth-loading">Loading…</div>;
  if (auth.status !== 'signed-in') return <AuthPage auth={auth} theme={theme} />;
  // A university department that signed up waits here until an administrator approves it.
  if (auth.user.account_type === 'department' && !auth.user.approved) {
    return <AwaitingApproval user={auth.user} onSignOut={auth.logout} />;
  }
  // Administrators and approved university departments only ever get the dashboard, never the
  // chat. The backend decides who they are (ADMIN_EMAILS in backend/.env; departments approved by
  // an administrator) and refuses the dashboard's data to everyone else.
  if (auth.user.admin || auth.user.account_type === 'department') {
    return (
      <AdminDashboard
        user={auth.user}
        token={auth.token}
        theme={theme}
        defaultPassword={auth.config.default_password}
        onChangePassword={auth.changePassword}
        onRename={auth.updateName}
        onSignOut={auth.logout}
      />
    );
  }
  // Students and guests: the chat.
  return <ChatBot auth={auth} theme={theme} onOpenAdmin={null} />;
}
