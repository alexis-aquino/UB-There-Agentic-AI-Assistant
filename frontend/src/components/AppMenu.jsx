import { useEffect, useRef, useState } from 'react';

/**
 * Every setting behind one "Menu" button, so the header stays clean: voice on/off, voice
 * settings, my questions, account, light/dark mode and sign out. Toggles keep the menu open
 * so you can see the change; the rest open their panel and close it.
 */
export default function AppMenu({
  userName,
  voiceOn,
  onToggleVoice,
  onVoiceSettings,
  onMyQuestions,
  onAccount,
  theme,
  onToggleTheme,
  onSignOut,
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const thenClose = (action) => () => {
    setOpen(false);
    action();
  };

  return (
    <div className="app-menu" ref={rootRef}>
      <button
        type="button"
        className="app-menu-button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        Menu
      </button>

      {open && (
        <div className="app-menu-panel" role="menu">
          <p className="app-menu-user">
            Signed in as <strong>{userName}</strong>
          </p>
          <button type="button" role="menuitemcheckbox" aria-checked={voiceOn} onClick={onToggleVoice}>
            <span className={`voice-led ${voiceOn ? 'is-on' : ''}`} aria-hidden="true" />
            Voice
            <span className="app-menu-state">{voiceOn ? 'On' : 'Off'}</span>
          </button>
          <button type="button" role="menuitem" onClick={thenClose(onVoiceSettings)}>
            Voice settings
          </button>
          <button type="button" role="menuitem" onClick={thenClose(onMyQuestions)}>
            My questions
          </button>
          <button type="button" role="menuitem" onClick={thenClose(onAccount)}>
            Account
          </button>
          <button type="button" role="menuitemcheckbox" aria-checked={theme === 'dark'} onClick={onToggleTheme}>
            Dark mode
            <span className="app-menu-state">{theme === 'dark' ? 'On' : 'Off'}</span>
          </button>
          <button type="button" role="menuitem" className="app-menu-signout" onClick={thenClose(onSignOut)}>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
