import AuthPage from './components/AuthPage.jsx';
import ChatBot from './components/ChatBot.jsx';
import useAuth from './hooks/useAuth.js';
import useTheme from './hooks/useTheme.js';

export default function App() {
  const auth = useAuth();
  const theme = useTheme();

  if (auth.status === 'loading') return <div className="auth-loading">Loading…</div>;
  if (auth.status !== 'signed-in') return <AuthPage auth={auth} theme={theme} />;
  return <ChatBot auth={auth} theme={theme} />;
}
