import { useEffect, useRef, useState } from 'react';
import Mascot3D from '../components/Mascot3D.jsx';
import useVoice from '../hooks/useVoice.js';
import { api } from '../api.js';

const GUEST_STARTERS = [
  'What are the admission requirements?',
  'How much is the tuition?',
  'When is the entrance exam?',
  'What courses are offered?',
];

const STUDENT_STARTERS = [
  'What happens if a student is absent for too many hours?',
  'Who prepares the schedule for major examinations?',
  'How many credit units is an overload?',
  'What is the policy on the school uniform?',
];

export default function StudentApp({ user, onSignOut }) {
  const isStudent = user.account_type === 'student';

  const [tab, setTab] = useState('chat');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [voiceOn, setVoiceOn] = useState(true);
  const [openTrace, setOpenTrace] = useState(null);

  const endRef = useRef(null);
  const inputRef = useRef(null);
  const { speak, stop, speaking, jawOpen, usingFallback } = useVoice({ enabled: voiceOn });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  const ask = async (question) => {
    if (!question || busy) return;
    stop();
    setMessages((prev) => [...prev, { sender: 'student', text: question }]);
    setInput('');
    setError(null);
    setBusy(true);

    try {
      const data = await api.chat(question, user.access_token, user.email);
      setMessages((prev) => [...prev, { sender: 'bot', ...data }]);
      if (voiceOn) speak(data.reply);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  };

  const starters = isStudent ? STUDENT_STARTERS : GUEST_STARTERS;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">UB</span>
          <div>
            <h1>UB There</h1>
            <p>
              {user.full_name || user.email}
              <span className="badge">{isStudent ? 'Current student' : 'Guest'}</span>
            </p>
          </div>
        </div>

        <nav className="header-actions">
          {[
            ['chat', 'Chat'],
            isStudent && ['audit', 'Document check'],
            ['track', 'Track inquiry'],
          ]
            .filter(Boolean)
            .map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={`chip-button ${tab === key ? 'is-on' : ''}`}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
          <button
            type="button"
            className={`chip-button ${voiceOn ? 'is-on' : ''}`}
            onClick={() => {
              if (voiceOn) stop();
              setVoiceOn(!voiceOn);
            }}
            aria-pressed={voiceOn}
          >
            {voiceOn ? 'Voice on' : 'Voice off'}
          </button>
          <button type="button" className="chip-button" onClick={onSignOut}>
            Sign out
          </button>
        </nav>
      </header>

      {tab === 'chat' && (
        <main className="app-main">
          <section className="stage">
            <Mascot3D jawOpen={jawOpen} speaking={speaking} thinking={busy} />
            <p className="stage-status">
              {busy ? 'Searching the handbook…' : speaking ? 'Speaking…' : 'Ready to help'}
            </p>
            {speaking && (
              <button type="button" className="link-button" onClick={stop}>
                Stop speaking
              </button>
            )}
            {usingFallback && speaking && (
              <p className="stage-note">Voice service unavailable — using the browser voice.</p>
            )}
          </section>

          <section className="conversation">
            <div className="chat-log">
              {messages.length === 0 && !busy && (
                <div className="empty-state">
                  <p>
                    {isStudent
                      ? 'Ask me about handbook policies. For example:'
                      : 'Ask me about applying to UB. For example:'}
                  </p>
                  <div className="starter-grid">
                    {starters.map((s) => (
                      <button key={s} type="button" className="starter" onClick={() => ask(s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m, idx) => (
                <article key={idx} className={`bubble bubble-${m.sender}`}>
                  <p className="bubble-text">{m.text ?? m.reply}</p>

                  {m.sender === 'bot' && (
                    <>
                      {m.escalated && (
                        <div className="escalation-note">
                          <strong>Referred to {m.department ?? 'the right office'}</strong>
                          <span>
                            Reference code <code>{m.reference_code}</code> — keep this to check
                            the status under “Track inquiry”.
                          </span>
                        </div>
                      )}
                      <div className="bubble-meta">
                        {m.sources?.length > 0 && <span className="chip">{m.sources[0]}</span>}
                        {typeof m.confidence === 'number' && m.confidence > 0 && (
                          <span className="chip chip-muted">
                            {Math.round(m.confidence * 100)}% confident
                          </span>
                        )}
                        {m.sources?.length > 1 && (
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => setOpenTrace(openTrace === idx ? null : idx)}
                          >
                            {openTrace === idx ? 'Hide sources' : 'All sources'}
                          </button>
                        )}
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => speak(m.reply ?? m.text)}
                        >
                          Replay
                        </button>
                      </div>
                      {openTrace === idx && (
                        <ul className="bubble-trace">
                          {m.sources.map((s) => (
                            <li key={s}>{s}</li>
                          ))}
                        </ul>
                      )}
                    </>
                  )}
                </article>
              ))}

              {busy && (
                <article className="bubble bubble-bot is-thinking">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </article>
              )}
              <div ref={endRef} />
            </div>

            {error && <p className="chat-error">{error}</p>}

            <div className="composer">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    ask(input.trim());
                  }
                }}
                placeholder="Ask a question…"
                aria-label="Your question"
                disabled={busy}
              />
              <button
                type="button"
                className="button-primary"
                onClick={() => ask(input.trim())}
                disabled={busy || !input.trim()}
              >
                Send
              </button>
            </div>
          </section>
        </main>
      )}

      {tab === 'audit' && isStudent && <DocumentAudit user={user} />}
      {tab === 'track' && <TrackInquiry />}
    </div>
  );
}

function DocumentAudit({ user }) {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [preview, setPreview] = useState(null);

  // Object URLs leak until revoked.
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const onFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setBusy(true);
    setError(null);
    setResult(null);
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(file);
    });

    try {
      setResult(await api.auditDocument(file, user.access_token));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      event.target.value = '';
    }
  };

  return (
    <main className="panel-page">
      <section className="panel">
        <h2>Check a document before you submit it</h2>
        <p className="panel-hint">
          Upload a photo or scan of a form. It is checked for legibility and you get a plain
          explanation of anything that needs fixing — so you can correct it before queueing.
        </p>

        <label className="file-drop">
          <input type="file" accept="image/*" onChange={onFile} disabled={busy} />
          <span>{busy ? 'Checking…' : 'Choose a photo or scan'}</span>
        </label>

        {error && <p className="chat-error">{error}</p>}

        {preview && (
          <div className="audit-layout">
            <img className="audit-preview" src={preview} alt="Uploaded document" />

            {result && (
              <div className="audit-results">
                <p className={`audit-verdict ${result.passed ? 'is-pass' : 'is-fail'}`}>
                  {result.passed
                    ? 'This looks good enough to submit.'
                    : 'This needs fixing before submitting.'}
                </p>
                <ul className="audit-findings">
                  {result.findings.map((f) => (
                    <li key={f.check} className={f.passed ? 'is-pass' : 'is-fail'}>
                      <strong>{f.check.replace(/_/g, ' ')}</strong>
                      <span>{f.detail}</span>
                      {f.how_to_fix && <em>{f.how_to_fix}</em>}
                    </li>
                  ))}
                </ul>
                {result.extracted_text && (
                  <details className="audit-text">
                    <summary>Text read from the document</summary>
                    <pre>{result.extracted_text}</pre>
                  </details>
                )}
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

function TrackInquiry() {
  const [code, setCode] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const lookup = async (e) => {
    e.preventDefault();
    if (!code.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.track(code.trim()));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const steps = ['new', 'sent', 'acknowledged', 'resolved'];
  const labels = {
    new: 'Received',
    sent: 'Sent to office',
    acknowledged: 'Being handled',
    resolved: 'Resolved',
  };

  return (
    <main className="panel-page">
      <section className="panel">
        <h2>Track an inquiry</h2>
        <p className="panel-hint">
          When a question can't be answered from the official documents, it's forwarded to the
          right office and you get a reference code. Enter it here to see where it stands.
        </p>

        <form className="composer" onSubmit={lookup}>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="UBT-2026-0001"
            aria-label="Reference code"
          />
          <button className="button-primary" disabled={busy || !code.trim()}>
            {busy ? 'Checking…' : 'Check status'}
          </button>
        </form>

        {error && <p className="chat-error">{error}</p>}

        {result && (
          <div className="track-result">
            <div className="track-head">
              <code>{result.reference_code}</code>
              <span className="chip">{labels[result.status] ?? result.status}</span>
            </div>

            <ol className="track-steps">
              {steps.map((s, i) => (
                <li
                  key={s}
                  className={i <= steps.indexOf(result.status) ? 'is-done' : ''}
                >
                  {labels[s]}
                </li>
              ))}
            </ol>

            <dl className="track-facts">
              <div>
                <dt>Your question</dt>
                <dd>{result.question}</dd>
              </div>
              <div>
                <dt>Handled by</dt>
                <dd>{result.department ?? 'Being assigned'}</dd>
              </div>
              {result.resolution_note && (
                <div>
                  <dt>Note from the office</dt>
                  <dd>{result.resolution_note}</dd>
                </div>
              )}
            </dl>
          </div>
        )}
      </section>
    </main>
  );
}
