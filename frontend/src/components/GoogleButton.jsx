import { useEffect, useRef, useState } from 'react';

const GIS_SRC = 'https://accounts.google.com/gsi/client';
let gisPromise = null;

function loadGoogleIdentity() {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!gisPromise) {
    gisPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = GIS_SRC;
      script.async = true;
      script.defer = true;
      script.onload = resolve;
      script.onerror = () => {
        gisPromise = null;
        reject(new Error('Could not load Google sign-in.'));
      };
      document.head.appendChild(script);
    });
  }
  return gisPromise;
}

// Google only accepts plain-http sign-in from localhost, so on a phone opening the PC's
// network address (http://192.168.x.x:5273) the button cannot work.
function googleCanRunHere() {
  const { protocol, hostname } = window.location;
  return protocol === 'https:' || hostname === 'localhost' || hostname === '127.0.0.1';
}

/**
 * Google's official sign-in button (Google Identity Services). It hands us an ID token
 * ("credential"), which the backend verifies with Google before signing the user in.
 * `domain` limits the account picker to the university's Google Workspace; the backend
 * enforces the same rule.
 */
export default function GoogleButton({ clientId, domain, theme, mode, onCredential, onError }) {
  const slotRef = useRef(null);
  const callbackRef = useRef(onCredential);
  const [failed, setFailed] = useState(false);
  callbackRef.current = onCredential;

  const usable = Boolean(clientId) && googleCanRunHere();

  useEffect(() => {
    if (!usable) return;
    let cancelled = false;

    loadGoogleIdentity()
      .then(() => {
        if (cancelled || !slotRef.current) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          hd: domain || undefined,
          callback: (response) => callbackRef.current(response.credential),
        });
        const dark = theme === 'dark';
        window.google.accounts.id.renderButton(slotRef.current, {
          type: 'standard',
          theme: dark ? 'filled_black' : 'outline',
          size: 'large',
          shape: 'rectangular',
          text: mode === 'signup' ? 'signup_with' : 'signin_with',
          locale: 'en',
          width: Math.min(slotRef.current.offsetWidth || 320, 400),
        });
      })
      .catch((err) => {
        setFailed(true);
        onError?.(err.message);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usable, clientId, domain, mode, theme]);

  if (!usable || failed) {
    return (
      <div className="google-unavailable">
        <button type="button" className="google-fallback" disabled>
          <GoogleMark />
          Sign in with UB Mail
        </button>
        <p>
          {failed
            ? 'UB Mail sign-in could not load. Check your connection.'
            : !clientId
              ? 'UB Mail sign-in is off — set GOOGLE_CLIENT_ID in backend/.env to turn it on.'
              : 'UB Mail sign-in only works on the PC itself (localhost) or over https.'}
        </p>
      </div>
    );
  }

  return <div ref={slotRef} className="google-slot" />;
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.2C12.5 13.6 17.8 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9h12.4c-.5 2.9-2.2 5.3-4.6 7l7.2 5.6c4.2-3.9 7.1-9.6 7.1-17z" />
      <path fill="#FBBC05" d="M10.6 28.7c-.5-1.4-.8-3-.8-4.7s.3-3.2.8-4.7l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.7 10.8l7.9-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.2-5.6c-2 1.4-4.7 2.3-8.7 2.3-6.2 0-11.5-4.1-13.4-9.8l-7.9 6.1C6.6 42.6 14.6 48 24 48z" />
    </svg>
  );
}
