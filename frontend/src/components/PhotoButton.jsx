import { useEffect, useRef, useState } from 'react';

const ACCEPT = 'image/jpeg,image/png,image/webp';

// Phones and tablets open their own camera app from a file input with `capture`; desktop
// browsers ignore `capture` and show a file picker, so there the webcam opens in the page.
const hasTouchCamera = () => window.matchMedia?.('(pointer: coarse)').matches ?? false;

function CameraIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="13" r="3.5" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

/** The webcam in the page: a live preview, then one still taken as a JPEG file. */
function CameraView({ onTaken, onClose }) {
  const videoRef = useRef(null);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let stream;
    let cancelled = false;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('This browser can’t use the camera here. Choose a photo instead.');
      return undefined;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1920 } }, audio: false })
      .then((s) => {
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        stream = s;
        videoRef.current.srcObject = s;
      })
      .catch((err) =>
        setError(
          err.name === 'NotAllowedError'
            ? 'Camera access was blocked. Allow it in the browser, or choose a photo instead.'
            : 'No camera could be opened. Choose a photo instead.',
        ),
      );
    // Always let the camera go: its light stays on otherwise.
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const take = () => {
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    canvas.toBlob((blob) => blob && onTaken(new File([blob], 'photo.jpg', { type: 'image/jpeg' })), 'image/jpeg', 0.9);
  };

  return (
    <div className="camera-backdrop" role="dialog" aria-modal="true" aria-label="Take a photo of the document">
      <div className="camera-sheet">
        {error ? (
          <p className="auth-error" role="alert">
            {error}
          </p>
        ) : (
          <video
            ref={videoRef}
            className="camera-video"
            autoPlay
            playsInline
            muted
            onLoadedMetadata={() => setReady(true)}
          />
        )}
        <p className="voice-hint">Lay the page flat in good light, with all of it in the frame.</p>
        <div className="ask-office-actions">
          {!error && (
            <button type="button" className="button-primary" onClick={take} disabled={!ready}>
              Take photo
            </button>
          )}
          <button type="button" className="link-button" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

/** The camera button by the question box: take a photo of a document, or choose one. */
export default function PhotoButton({ onPhoto, disabled }) {
  const [open, setOpen] = useState(false);
  const [camera, setCamera] = useState(false);
  const rootRef = useRef(null);
  const takeRef = useRef(null);
  const chooseRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const picked = (e) => {
    const file = e.target.files[0];
    e.target.value = '';
    if (file) onPhoto(file);
  };

  const takePhoto = () => {
    setOpen(false);
    if (hasTouchCamera()) takeRef.current?.click();
    else setCamera(true);
  };

  return (
    <div className="photo-button" ref={rootRef}>
      <input ref={takeRef} type="file" accept={ACCEPT} capture="environment" hidden onChange={picked} />
      <input ref={chooseRef} type="file" accept={ACCEPT} hidden onChange={picked} />
      <button
        type="button"
        className="photo-button-icon"
        aria-label="Check a document"
        aria-haspopup="menu"
        aria-expanded={open}
        title="Check a document against the handbook. Anything typed in the box goes along as a note."
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
      >
        <CameraIcon />
      </button>

      {open && (
        <div className="app-menu-panel photo-button-panel" role="menu">
          <p className="app-menu-user">Check a document against the handbook</p>
          <button type="button" role="menuitem" onClick={takePhoto}>
            Take a photo
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              chooseRef.current?.click();
            }}
          >
            Choose a photo
          </button>
        </div>
      )}

      {camera && (
        <CameraView
          onClose={() => setCamera(false)}
          onTaken={(file) => {
            setCamera(false);
            onPhoto(file);
          }}
        />
      )}
    </div>
  );
}
