import { useEffect, useRef, useState } from 'react';
import AccountPanel from './AccountPanel.jsx';
import AskOffice from './AskOffice.jsx';
import AvatarStage from './AvatarStage.jsx';
import SourceView from './SourceView.jsx';
import AppMenu from './AppMenu.jsx';
import TicketsPanel from './TicketsPanel.jsx';
import VoicePanel from './VoicePanel.jsx';
import useVoice from '../hooks/useVoice.js';
import { API_URL } from '../api.js';

// The sidebar "index": frequently consulted topics, each a ready-made question.
const STARTERS = [
  { topic: 'Attendance', question: 'What happens if a student is absent for too many hours?' },
  { topic: 'Examinations', question: 'Who prepares the schedule for major examinations?' },
  { topic: 'Enrollment', question: 'How many credit units is an overload?' },
  { topic: 'Uniform', question: 'What is the policy on the school uniform?' },
];

const VOICE_KEY = 'ub-there-voice';

function sourceLabel(source) {
  // "studenthandbook.pdf p.99" -> "Student handbook, p. 99"
  const match = source.match(/^(.+?)(?:\s+p\.(\d+))?$/);
  let name = (match?.[1] ?? source).replace(/\.(pdf|docx?|txt|md)$/i, '').replace(/[_-]+/g, ' ');
  name = name.replace(/([a-z])(handbook|manual|guide|policy|policies|catalog)\b/gi, '$1 $2');
  name = name.charAt(0).toUpperCase() + name.slice(1);
  return match?.[2] ? `${name}, p. ${match[2]}` : name;
}

// The model is asked for plain text, but small models slip into markdown now and then.
function displayText(text) {
  return text.replace(/\*\*(.+?)\*\*/g, '$1').replace(/^#+\s*/gm, '').replace(/^\s*[*-]\s+/gm, '• ');
}

function readSavedVoice() {
  try {
    return localStorage.getItem(VOICE_KEY);
  } catch {
    return null;
  }
}

export default function ChatBot({ auth, theme, onOpenAdmin }) {
  const { user, token, config, changePassword, logout } = auth;
  // One conversation thread per signed-in user, fresh on each page load.
  const [sessionId] = useState(() => `user-${user.id}-${Math.random().toString(36).slice(2, 8)}`);
  const [showAccount, setShowAccount] = useState(false);
  const [showTickets, setShowTickets] = useState(false);
  const [askingFor, setAskingFor] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);
  const [voiceOn, setVoiceOn] = useState(true);
  const [showVoicePanel, setShowVoicePanel] = useState(false);
  const [voiceCatalog, setVoiceCatalog] = useState(null);
  const [voiceId, setVoiceId] = useState(readSavedVoice);
  const [previewing, setPreviewing] = useState(null);
  const [openSource, setOpenSource] = useState(null);

  const endRef = useRef(null);
  const inputRef = useRef(null);
  const { speak, stop, beginStream, feedStream, endStream, speaking, loading, usingFallback } = useVoice({
    enabled: voiceOn,
    voice: voiceId,
  });

  useEffect(() => {
    if (!loading) setPreviewing(null);
  }, [loading]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isSending]);

  useEffect(() => {
    fetch(`${API_URL}/api/voice/voices`)
      .then((r) => (r.ok ? r.json() : null))
      .then((catalog) => {
        setVoiceCatalog(catalog);
        // A saved voice that the server no longer offers falls back to the default.
        if (catalog && !catalog.voices.some((v) => v.id === readSavedVoice())) setVoiceId(null);
      })
      .catch(() => setVoiceCatalog(null));
  }, [showVoicePanel]);

  const chooseVoice = (id) => {
    setVoiceId(id);
    try {
      localStorage.setItem(VOICE_KEY, id);
    } catch {
      // Private mode: the choice lasts until reload.
    }
  };

  const previewVoice = (text, id) => {
    setPreviewing(id);
    speak(text, { voice: id, force: true });
  };

  const selectedVoice =
    voiceId ?? voiceCatalog?.voices.find((v) => v.default)?.id ?? null;

  const ask = async (question) => {
    if (!question || isSending) return;

    stop();
    setInput('');
    setError(null);
    setIsSending(true);
    // The reply streams into this message as the model writes it.
    const id = Date.now();
    setMessages((prev) => [
      ...prev,
      { sender: 'student', text: question },
      { id, sender: 'bot', text: '', streaming: true, question, sources: [], citations: [] },
    ]);
    const update = (changes) =>
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...changes } : m)));

    let text = '';
    try {
      const res = await fetch(`${API_URL}/api/chat/stream`, {
        method: 'POST',
        // Signed in, so the admin's inquiry report knows who asked.
        headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }) },
        body: JSON.stringify({ message: question, session_id: sessionId }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Request failed (${res.status})`);
      }

      if (voiceOn) beginStream();
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let newline;
        while ((newline = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, newline).trim();
          buffer = buffer.slice(newline + 1);
          if (!line) continue;
          const event = JSON.parse(line);
          if (event.type === 'delta') {
            text += event.text;
            update({ text });
            feedStream(text);
          } else if (event.type === 'done') {
            text = event.reply;
            update({
              text,
              streaming: false,
              sources: event.sources ?? [],
              confidence: event.confidence,
              citations: event.citations ?? [],
              canReroute: Boolean(event.can_reroute),
              inquiryId: event.inquiry_id ?? null,
            });
            endStream(text);
          } else if (event.type === 'error') {
            throw new Error(event.detail);
          }
        }
      }
    } catch (err) {
      stop();
      setError(err.message);
      // Keep whatever arrived; drop the bubble if nothing did.
      setMessages((prev) =>
        text ? prev.map((m) => (m.id === id ? { ...m, streaming: false } : m)) : prev.filter((m) => m.id !== id),
      );
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    ask(input.trim());
  };

  const answering = messages.some((m) => m.streaming && m.text);
  const status = isSending
    ? answering
      ? 'Answering…'
      : 'Consulting the handbook…'
    : speaking
      ? 'Reading the answer aloud…'
      : 'Ready for a question';
  const firstName = user.name.split(' ')[0];

  const starterList = (className) => (
    <ol className={className}>
      {STARTERS.map((s, i) => (
        <li key={s.topic}>
          <button type="button" onClick={() => ask(s.question)} disabled={isSending}>
            <span className="index-num">§{i + 1}</span>
            <span className="index-topic">{s.topic}</span>
            <span className="index-question">{s.question}</span>
          </button>
        </li>
      ))}
    </ol>
  );

  return (
    <div className="app-shell">
      <header className="masthead">
        <div className="masthead-brand">
          <span className="seal" aria-hidden="true">UB</span>
          <div>
            <h1>UB There</h1>
            <p className="label">University of Batangas</p>
          </div>
        </div>

        <AppMenu
          userName={user.name}
          voiceOn={voiceOn}
          onToggleVoice={() => {
            if (voiceOn) stop();
            setVoiceOn(!voiceOn);
          }}
          onVoiceSettings={() => setShowVoicePanel(true)}
          onMyQuestions={() => setShowTickets(true)}
          onAccount={() => setShowAccount(true)}
          onAdmin={onOpenAdmin}
          theme={theme.theme}
          onToggleTheme={theme.toggle}
          onSignOut={() => {
            stop();
            logout();
          }}
        />
      </header>

      {user.default_password && !showAccount && (
        <div className="notice" role="status">
          <span className="label">Notice</span>
          <span>You are still using the starting password. Change it to keep your account yours.</span>
          <button type="button" className="link-button" onClick={() => setShowAccount(true)}>
            Change password
          </button>
        </div>
      )}

      {showAccount && (
        <AccountPanel
          user={user}
          defaultPassword={config.default_password}
          onChangePassword={changePassword}
          onClose={() => setShowAccount(false)}
        />
      )}

      {showTickets && <TicketsPanel token={token} onClose={() => setShowTickets(false)} />}

      {showVoicePanel && (
        <VoicePanel
          catalog={voiceCatalog}
          selected={selectedVoice}
          onSelect={chooseVoice}
          onPreview={previewVoice}
          previewing={previewing}
          onClose={() => setShowVoicePanel(false)}
        />
      )}

      <div className="desk">
        <AvatarStage thinking={isSending} speaking={speaking} />

        <main className="page">
          {messages.length === 0 && !isSending ? (
            <section className="page-cover">
              <p className="label">Good to see you, {firstName}</p>
              <h2 className="page-title">
                Ask the <em>handbook.</em>
              </h2>
              <p className="page-lede">
                Ask anything about university policies. Answers come from the university’s own
                documents, with the source shown — so you can check it yourself.
              </p>
              <div className="page-starters">
                <p className="label">Or start with</p>
                {starterList('index-list')}
              </div>
            </section>
          ) : (
            <ol className="transcript">
              {messages.map((m, idx) => (
                <li key={idx} className={`entry entry-${m.sender === 'bot' ? 'a' : 'q'}`}>
                  <span className="entry-mark" aria-hidden="true">
                    {m.sender === 'bot' ? 'A.' : 'Q.'}
                  </span>
                  <div className="entry-body">
                    {m.streaming && !m.text ? (
                      <p className="thinking">
                        Consulting the handbook
                        <span className="thinking-rule" aria-hidden="true" />
                      </p>
                    ) : (
                      <p className="entry-text">
                        {displayText(m.text)}
                        {m.streaming && <span className="typing-caret" aria-hidden="true" />}
                      </p>
                    )}

                    {m.sender === 'bot' && !m.streaming && (
                      <div className="entry-meta">
                        {m.sources?.length > 0 && (
                          <span className="citation">{sourceLabel(m.sources[0])}</span>
                        )}
                        {typeof m.confidence === 'number' && m.confidence > 0 && (
                          <span className="meta-fact">{Math.round(m.confidence * 100)}% match</span>
                        )}
                        <span className="meta-actions">
                          {m.citations?.length > 0 && (
                            <button
                              type="button"
                              className="link-button"
                              onClick={() => setOpenSource(openSource === idx ? null : idx)}
                              aria-expanded={openSource === idx}
                            >
                              {openSource === idx ? 'Hide source' : 'Where I got this'}
                            </button>
                          )}
                          <button type="button" className="link-button" onClick={() => speak(m.text)}>
                            Read aloud
                          </button>
                        </span>
                      </div>
                    )}

                    {m.canReroute && !m.ticket && askingFor !== idx && (
                      <button
                        type="button"
                        className="chip-button ask-office-open"
                        onClick={() => setAskingFor(idx)}
                      >
                        Ask an office
                      </button>
                    )}
                    {askingFor === idx && (
                      <AskOffice
                        question={m.question}
                        inquiryId={m.inquiryId}
                        token={token}
                        onCancel={() => setAskingFor(null)}
                        onSent={(ticket) => {
                          setMessages((prev) =>
                            prev.map((msg, i) => (i === idx ? { ...msg, ticket } : msg)),
                          );
                          setAskingFor(null);
                        }}
                      />
                    )}
                    {m.ticket && (
                      <p className="ask-office-sent">
                        Sent to the {m.ticket.office_name} as {m.ticket.ref}. Their answer will
                        appear under “My questions”.
                      </p>
                    )}

                    {openSource === idx && <SourceView citations={m.citations} />}
                  </div>
                </li>
              ))}

              <li ref={endRef} className="transcript-end" aria-hidden="true" />
            </ol>
          )}

          {error && (
            <p className="chat-error" role="alert">
              {error}
            </p>
          )}

          <div className="composer-dock">
            <div className="chat-status" role="status">
              <span className={`status-dot ${isSending || speaking ? 'is-busy' : ''}`} aria-hidden="true" />
              <span>{status}</span>
              {speaking && (
                <button type="button" className="link-button" onClick={stop}>
                  Stop
                </button>
              )}
              {usingFallback && speaking && (
                <span className="chat-status-note">Voice service unavailable — using the browser voice.</span>
              )}
            </div>
          <form className="composer" onSubmit={handleSubmit}>
            <label className="composer-field">
              <span className="label">Your question</span>
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="e.g. Can I take an exam I missed because I was sick?"
                disabled={isSending}
                maxLength={2000}
              />
            </label>
            <button type="submit" className="button-primary" disabled={isSending || !input.trim()}>
              Ask
            </button>
          </form>
          </div>
        </main>
      </div>
    </div>
  );
}
