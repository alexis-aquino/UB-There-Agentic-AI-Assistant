const PREVIEW_TEXT = "Hi! I'm UB There. Ask me anything about the student handbook.";

/** Pick which AI voice reads answers aloud. Voice recording lives in the backend only. */
export default function VoicePanel({ catalog, selected, onSelect, onPreview, previewing }) {
  const provider = catalog?.provider;
  const voices = catalog?.voices ?? [];

  return (
    <section className="voice-panel" aria-label="Voice settings">
      <div className="voice-panel-head">
        <h2>Voice</h2>
      </div>

      {!catalog && <p className="voice-hint">Loading voices…</p>}

      {provider === 'off' && (
        <p className="voice-hint">Voice output is turned off on the server, so answers are text only.</p>
      )}
      {provider === 'xtts' && (
        <p className="voice-hint">The server is using a custom cloned voice, so the choices below don’t apply.</p>
      )}

      {provider === 'piper' && (
        <>
          <p className="voice-hint">Choose the AI voice that reads answers aloud.</p>
          <ul className="voice-options" role="radiogroup" aria-label="AI voices">
            {voices.map((voice) => {
              const isSelected = voice.id === selected;
              return (
                <li key={voice.id} className={`voice-option ${isSelected ? 'is-selected' : ''}`}>
                  <label>
                    <input
                      type="radio"
                      name="ai-voice"
                      value={voice.id}
                      checked={isSelected}
                      onChange={() => onSelect(voice.id)}
                    />
                    <span className="voice-option-name">{voice.name}</span>
                    <span className="voice-option-accent">
                      {voice.accent}
                      {voice.default && ' · default'}
                    </span>
                  </label>
                  <button
                    type="button"
                    className="chip-button"
                    onClick={() => onPreview(PREVIEW_TEXT, voice.id)}
                    disabled={previewing}
                  >
                    {previewing === voice.id ? 'Loading…' : 'Preview'}
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="voice-hint">
            New voices download the first time you use them (about 60 MB), so the first preview can take a moment.
          </p>
        </>
      )}
    </section>
  );
}
