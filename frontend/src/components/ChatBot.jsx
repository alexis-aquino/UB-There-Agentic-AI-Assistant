import { useEffect, useRef, useState } from 'react';
import './ChatBot.css';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export default function ChatBot() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  const sendMessage = async () => {
    const question = input.trim();
    if (!question || isSending) return;

    setMessages((prev) => [...prev, { sender: 'student', text: question }]);
    setInput('');
    setError(null);
    setIsSending(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `Request failed (${res.status})`);

      setMessages((prev) => [...prev, { sender: 'bot', text: data.reply }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-page">
      <header className="chat-header">
        <h1>UB There</h1>
        <p>Ask about academic policies, grading, enrollment, and tuition.</p>
      </header>

      <div className="chat-log">
        {messages.length === 0 && !isSending && (
          <p className="chat-empty">
            Try: &ldquo;What is the tuition refund policy if I withdraw in week 3?&rdquo;
          </p>
        )}

        {messages.map((m, idx) => (
          <div key={idx} className={`bubble bubble-${m.sender}`}>
            {m.text}
          </div>
        ))}

        {isSending && <div className="bubble bubble-bot chat-thinking">Checking the handbook…</div>}
        <div ref={endRef} />
      </div>

      {error && <div className="chat-error">{error}</div>}

      <div className="chat-input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about academic policies…"
          disabled={isSending}
        />
        <button onClick={sendMessage} disabled={isSending || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
