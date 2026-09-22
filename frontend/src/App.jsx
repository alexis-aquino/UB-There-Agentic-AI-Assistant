import { useState } from 'react';
import SignIn from './pages/SignIn.jsx';
import StudentApp from './pages/StudentApp.jsx';
import AdminApp from './pages/AdminApp.jsx';
import { session } from './api.js';

export default function App() {
  const [user, setUser] = useState(() => session.getUser());
  const [admin, setAdmin] = useState(() => session.getAdmin());

  const signInUser = (value) => {
    session.setUser(value);
    setUser(value);
  };

  const signInAdmin = (value) => {
    session.setAdmin(value);
    setAdmin(value);
  };

  const signOut = () => {
    session.setUser(null);
    session.setAdmin(null);
    setUser(null);
    setAdmin(null);
  };

  if (admin) return <AdminApp admin={admin} onSignOut={signOut} />;
  if (user) return <StudentApp user={user} onSignOut={signOut} />;
  return <SignIn onUser={signInUser} onAdmin={signInAdmin} />;
}
