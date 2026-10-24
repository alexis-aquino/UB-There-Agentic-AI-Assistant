import { useEffect, useState } from 'react';
import AdminDashboard from './components/AdminDashboard.jsx';
import AuthPage from './components/AuthPage.jsx';
import ChatBot from './components/ChatBot.jsx';
import useAuth from './hooks/useAuth.js';
import useTheme from './hooks/useTheme.js';

// The admin dashboard lives at #admin, so it can be bookmarked and the Back button works.
const onAdminPage = () => window.location.hash.split('/')[0] === '#admin'; // #admin, or #admin/<tab>

export default function App() {
  const auth = useAuth();
  const theme = useTheme();
  const [admin, setAdmin] = useState(onAdminPage);

  useEffect(() => {
    const onHash = () => setAdmin(onAdminPage());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  if (auth.status === 'loading') return <div className="auth-loading">Loading…</div>;
  if (auth.status !== 'signed-in') return <AuthPage auth={auth} theme={theme} />;
  // The backend decides who is an admin (ADMIN_EMAILS in backend/.env, UB accounts only) and
  // refuses the dashboard's data to everyone else; this only decides what to show.
  const isAdmin = Boolean(auth.user.admin);
  const showAdmin = admin && isAdmin;
  return (
    <>
      {showAdmin && (
        <AdminDashboard user={auth.user} token={auth.token} theme={theme} onBack={() => (window.location.hash = '')} />
      )}
      {/* Stays mounted under the dashboard, so the conversation survives a visit to it. */}
      <div hidden={showAdmin}>
        <ChatBot auth={auth} theme={theme} onOpenAdmin={isAdmin ? () => (window.location.hash = 'admin') : null} />
      </div>
    </>
  );
}
