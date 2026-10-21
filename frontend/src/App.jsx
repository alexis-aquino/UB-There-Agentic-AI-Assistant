import { useEffect, useState } from 'react';
import AdminDashboard from './components/AdminDashboard.jsx';
import AuthPage from './components/AuthPage.jsx';
import ChatBot from './components/ChatBot.jsx';
import useAuth from './hooks/useAuth.js';
import useTheme from './hooks/useTheme.js';

// The admin dashboard lives at #admin, so it can be bookmarked and the Back button works.
const onAdminPage = () => window.location.hash.split('/')[0] === '#admin'; // #admin, or #admin/<tab>

// Who sees "Admin dashboard" in the menu (frontend/.env). Only hides the link: with no backend
// admin role yet, anyone signed in can still open #admin — it shows sample data only.
const ADMIN_EMAILS = (import.meta.env.VITE_ADMIN_EMAILS ?? '')
  .split(',')
  .map((email) => email.trim().toLowerCase())
  .filter(Boolean);

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
  const isAdmin = ADMIN_EMAILS.includes(auth.user.email.toLowerCase());
  return (
    <>
      {admin && <AdminDashboard user={auth.user} theme={theme} onBack={() => (window.location.hash = '')} />}
      {/* Stays mounted under the dashboard, so the conversation survives a visit to it. */}
      <div hidden={admin}>
        <ChatBot auth={auth} theme={theme} onOpenAdmin={isAdmin ? () => (window.location.hash = 'admin') : null} />
      </div>
    </>
  );
}
